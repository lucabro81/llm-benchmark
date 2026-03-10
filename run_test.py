#!/usr/bin/env python3
"""CLI runner for LLM benchmark.

Usage:
    python run_test.py --model <model> [--fixture <name>] [--runs <n>]

Arguments:
    --model    (required) Ollama model name (e.g., qwen2.5-coder:14b-instruct-q8_0)
    --fixture  (optional) Task name under tasks/. Runs ALL if omitted.
    --runs     (optional) Number of runs per task (default: 3)
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Optional, Type

from rich.console import Console

from src.creation.nuxt_form_oneshot.test_runner import BenchmarkResult

OUTPUT_DIR = Path("results")
TASKS_DIR = Path("tasks")

# Explicit mapping: task directory name → test runner module path
# nuxt-form diagnostic battery (A → B → C → D → E)
_RUNNER_MAP = {
    "nuxt-form-oneshot":         "src.creation.nuxt_form_oneshot.test_runner",
    "nuxt-form-agent-guided":    "src.agent.nuxt_form_agent_guided.test_runner",
    "nuxt-form-agent-twofiles":  "src.agent.nuxt_form_agent_twofiles.test_runner",
    "nuxt-form-agent-rag":       "src.agent.nuxt_form_agent_rag.test_runner",
    "nuxt-form-agent-full":      "src.agent.nuxt_form_agent_full.test_runner",
}

console = Console()


# ---------------------------------------------------------------------------
# Fixture discovery
# ---------------------------------------------------------------------------

def discover_fixtures(base_dir: Path = TASKS_DIR) -> List[Path]:
    """Return fixtures ordered as defined in _RUNNER_MAP (A → E).

    A valid fixture must contain a validation_spec.json file.
    Unknown fixtures (not in _RUNNER_MAP) are appended alphabetically at the end.

    Args:
        base_dir: Directory to search for fixtures

    Returns:
        Ordered list of fixture Paths

    Raises:
        FileNotFoundError: If base_dir does not exist or contains no valid fixtures
    """
    if not base_dir.exists():
        raise FileNotFoundError(f"Fixtures directory not found: {base_dir}")

    _runner_order = list(_RUNNER_MAP.keys())

    def _sort_key(p: Path) -> tuple:
        try:
            return (0, _runner_order.index(p.name))
        except ValueError:
            return (1, p.name)

    fixtures = sorted(
        [p for p in base_dir.iterdir() if p.is_dir() and (p / "validation_spec.json").exists()],
        key=_sort_key,
    )

    if not fixtures:
        raise FileNotFoundError(f"No valid fixtures found in {base_dir}")

    return fixtures


def _get_runner_module(fixture_path: Path):
    """Import the runner module for the given fixture.

    Args:
        fixture_path: Path to the fixture directory

    Returns:
        Imported runner module (exposes a test class and format_run)

    Raises:
        ValueError: If fixture has no registered runner
    """
    import importlib

    fixture_name = fixture_path.name
    module_path = _RUNNER_MAP.get(fixture_name)
    if not module_path:
        raise ValueError(
            f"No runner registered for fixture '{fixture_name}'. "
            f"Add it to _RUNNER_MAP in run_test.py."
        )
    return importlib.import_module(module_path)


def _get_runner_class(module) -> Type:
    """Return the test class from an imported runner module."""
    if hasattr(module, "AgentTest"):
        return module.AgentTest
    return module.CreationTest


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _make_session_dir(session_name: Optional[str]) -> Path:
    """Compute (but do not create) the session output directory path.

    Pattern: OUTPUT_DIR/session__{name}__{ts} if name provided,
             OUTPUT_DIR/session__{ts} otherwise.

    Args:
        session_name: Optional human-readable label for the session.

    Returns:
        Path object (not yet created on disk).
    """
    ts = int(time.time())
    if session_name:
        return OUTPUT_DIR / f"session__{session_name}__{ts}"
    return OUTPUT_DIR / f"session__{ts}"


def show_header(model: str, fixtures: List[Path], runs: int):
    """Display benchmark header."""
    fixture_names = ", ".join(f.name for f in fixtures)
    console.print("\n[bold cyan]╔════════════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║  LLM Benchmark     ║[/bold cyan]")
    console.print("[bold cyan]╚════════════════════════════════════════════╝[/bold cyan]\n")
    console.print(f"Model:    [yellow]{model}[/yellow]")
    console.print(f"Fixtures: [yellow]{fixture_names}[/yellow]")
    console.print(f"Runs:     [yellow]{runs} per fixture[/yellow]\n")


def show_fixture_header(fixture_name: str, index: int, total: int):
    """Display fixture section header (only when running multiple fixtures)."""
    if total > 1:
        console.print(f"\n[bold]{'═' * 46}[/bold]")
        console.print(f"[bold]Fixture {index}/{total}: {fixture_name}[/bold]")
        console.print(f"[bold]{'═' * 46}[/bold]")




def show_fixture_summary(results: List[BenchmarkResult], fixture_name: str):
    """Display summary statistics for a single fixture."""
    avg_score = sum(r.final_score for r in results) / len(results)
    avg_pattern = sum(r.pattern_score for r in results) / len(results)
    avg_naming = sum(r.naming_score for r in results) / len(results)
    avg_speed = sum(r.tokens_per_sec for r in results) / len(results)
    avg_duration = sum(r.duration_sec for r in results) / len(results)
    success_count = sum(1 for r in results if r.compiles)
    success_rate = (success_count / len(results)) * 100

    console.print(f"[bold]Summary: {fixture_name}[/bold]")
    console.print(f"  Avg Final Score:   [bold cyan]{avg_score:.2f}/10[/bold cyan]")
    console.print(f"  Avg Pattern Score: {avg_pattern:.2f}/10")
    console.print(f"  Avg Naming Score:  {avg_naming:.2f}/10")
    console.print(f"  Avg Speed:         {avg_speed:.1f} tok/s")
    console.print(f"  Avg Duration:      {avg_duration:.1f}s")
    console.print(f"  Compile Success:   {success_rate:.0f}% ({success_count}/{len(results)} runs)")

    if avg_score < 7.0:
        console.print(
            f"\n[yellow]⚠ Warning: Average score is {avg_score:.1f}/10 (target ≥7.0)[/yellow]"
        )
        console.print("[yellow]  → Model may need fine-tuning or prompt adjustment[/yellow]")


def show_overall_summary(all_results: List[BenchmarkResult], fixture_count: int):
    """Display aggregate summary across all fixtures."""
    avg_score = sum(r.final_score for r in all_results) / len(all_results)
    avg_speed = sum(r.tokens_per_sec for r in all_results) / len(all_results)
    success_count = sum(1 for r in all_results if r.compiles)
    success_rate = (success_count / len(all_results)) * 100

    console.print(f"\n[bold]{'═' * 46}[/bold]")
    console.print("[bold]Overall Summary (All Fixtures)[/bold]")
    console.print(f"[bold]{'═' * 46}[/bold]")
    console.print(f"  Total Fixtures:    {fixture_count}")
    console.print(f"  Total Runs:        {len(all_results)}")
    console.print(f"  Avg Final Score:   [bold cyan]{avg_score:.2f}/10[/bold cyan]")
    console.print(f"  Avg Speed:         {avg_speed:.1f} tok/s")
    console.print(f"  Compile Success:   {success_rate:.0f}% ({success_count}/{len(all_results)} runs)")


# ---------------------------------------------------------------------------
# Results saving
# ---------------------------------------------------------------------------

def _is_agent_result(result) -> bool:
    """Return True if result is an agent benchmark result (has tool_call_log)."""
    return hasattr(result, "tool_call_log")


def _save_agent_results(
    results: list,
    model: str,
    fixture_name: str,
    requested_runs: int,
    agent_output_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """Save agent results to a folder with summary.json + steps.jsonl.

    Folder name: {model_safe}__{fixture}__{n_runs}runs__{unix_ts}

    Args:
        results: List of AgentBenchmarkResult
        model: Model name
        fixture_name: Fixture name
        requested_runs: Number of runs requested (from --runs)
        agent_output_dir: Pre-created output folder (e.g. from run_fixture for
            prompt log co-location). If None, a new folder is created.
        output_dir: Base directory for output. Defaults to OUTPUT_DIR.

    Returns:
        Path to the output folder.
    """
    base = output_dir if output_dir is not None else OUTPUT_DIR
    base.mkdir(parents=True, exist_ok=True)
    if agent_output_dir is None:
        model_safe = model.replace(":", "__")
        unix_ts = int(time.time())
        agent_output_dir = base / f"{model_safe}__{fixture_name}__{requested_runs}runs__{unix_ts}"
    agent_output_dir.mkdir(parents=True, exist_ok=True)

    # summary.json — metadata + full run results (including tool_call_log with args)
    summary = {
        "model": model,
        "fixture": fixture_name,
        "n_runs": requested_runs,
        "runs": [r.__dict__ for r in results],
    }
    with (agent_output_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # steps.jsonl — compact per-step data across all runs (no args)
    with (agent_output_dir / "steps.jsonl").open("w", encoding="utf-8") as f:
        for result in results:
            run_num = result.run_number
            for entry in result.tool_call_log:
                step_entry = {
                    "run": run_num,
                    "step": entry.get("step"),
                    "tool": entry.get("tool"),
                    "compile_passed": entry.get("compile_passed"),
                    "duration_sec": entry.get("duration_sec"),
                    "context_chars": entry.get("context_chars"),
                    "result_summary": entry.get("result_summary"),
                }
                f.write(json.dumps(step_entry) + "\n")

    return agent_output_dir


def save_results(
    results: List[BenchmarkResult],
    model: str,
    fixture_name: str,
    requested_runs: Optional[int] = None,
    agent_output_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """Save results for one fixture.

    For single-shot tests: writes a JSON file (array of run results).
    For agent tests: writes a folder with summary.json + steps.jsonl.

    Args:
        results: List of results for all runs of this fixture
        model: Model name (used in filename/folder name)
        fixture_name: Fixture name (used in filename/folder name)
        requested_runs: Number of runs requested (--runs N). Defaults to len(results).
        agent_output_dir: Pre-created folder for agent output (optional; used when
            prompt logs were already written there during the run).
        output_dir: Base directory for output. Defaults to OUTPUT_DIR.

    Returns:
        Path to saved JSON file (single-shot) or folder (agent).
    """
    n_runs = requested_runs if requested_runs is not None else len(results)
    base = output_dir if output_dir is not None else OUTPUT_DIR

    if results and _is_agent_result(results[0]):
        return _save_agent_results(results, model, fixture_name, n_runs, agent_output_dir, base)

    # Single-shot: flat JSON file
    base.mkdir(parents=True, exist_ok=True)
    timestamp = results[0].timestamp.replace(":", "-")
    model_safe = model.replace(":", "__")
    output_file = base / f"{model_safe}__{fixture_name}__{timestamp}.json"
    with open(output_file, "w") as f:
        json.dump([r.__dict__ for r in results], f, indent=2)
    return output_file


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_fixture(
    model: str,
    fixture_path: Path,
    runs: int,
    runner_module,
    log_prompts: bool = False,
    agent_output_dir: Optional[Path] = None,
    output_base: Optional[Path] = None,
) -> Optional[List[BenchmarkResult]]:
    """Run benchmark for a single fixture.

    Args:
        model: Ollama model name.
        fixture_path: Path to the task directory.
        runs: Number of runs to execute.
        runner_module: Imported runner module.
        log_prompts: If True, write per-step prompt logs to prompts.jsonl.
        agent_output_dir: For agent tests — pre-created output folder where
            prompts.jsonl will be written (all runs share the same file).
    """
    runner_class = _get_runner_class(runner_module)
    try:
        test = runner_class(model=model, fixture_path=fixture_path)
    except FileNotFoundError as e:
        console.print(f"[red]✗ Error loading fixture '{fixture_path.name}': {e}[/red]")
        console.print("[yellow]  → Skipping this fixture[/yellow]")
        return None

    is_agent = hasattr(runner_module, "AgentTest")

    results = []
    for i in range(runs):
        console.print(f"[dim]── Run {i + 1}/{runs} ──[/dim]")
        run_kwargs = {"run_number": i + 1}

        if log_prompts and is_agent and agent_output_dir is not None:
            # All runs append to the same prompts.jsonl inside the output folder.
            prompt_log = agent_output_dir / "prompts.jsonl"
            if hasattr(test, "run") and "prompt_log_path" in test.run.__code__.co_varnames:
                run_kwargs["prompt_log_path"] = prompt_log
                if i == 0:
                    console.print(f"[dim]  prompt log → {prompt_log}[/dim]")
        elif log_prompts and not is_agent:
            # Single-shot: legacy per-run log
            if hasattr(test, "run") and "prompt_log_path" in test.run.__code__.co_varnames:
                model_safe = model.replace(":", "_").replace(".", "-")
                log_base = output_base if output_base is not None else OUTPUT_DIR
                log_base.mkdir(exist_ok=True)
                run_kwargs["prompt_log_path"] = (
                    log_base / f"{model_safe}__{fixture_path.name}__run{i+1}__prompts.jsonl"
                )
                console.print(f"[dim]  prompt log → {run_kwargs['prompt_log_path']}[/dim]")

        result = test.run(**run_kwargs)
        results.append(result)
        runner_module.format_run(result)

    return results


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="LLM Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_test.py --model qwen2.5-coder:7b-instruct-q8_0\n"
            "  python run_test.py --models qwen2.5-coder:7b qwen2.5-coder:14b\n"
            "  python run_test.py --models qwen2.5-coder:7b --fixture nuxt-form-oneshot\n"
            "  python run_test.py --models qwen2.5-coder:7b --runs 1 --session-name my-run\n"
        ),
    )
    model_group = parser.add_mutually_exclusive_group(required=True)
    model_group.add_argument(
        "--models",
        nargs="+",
        metavar="MODEL",
        dest="models",
        help="One or more Ollama model names",
    )
    model_group.add_argument(
        "--model",
        metavar="MODEL",
        dest="_model_alias",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--fixture",
        default=None,
        metavar="NAME",
        help="Task name under tasks/ (runs ALL if omitted)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        metavar="N",
        help="Number of runs per fixture (default: 3)",
    )
    parser.add_argument(
        "--session-name",
        default=None,
        metavar="NAME",
        help="Human-readable label for the session folder (optional)",
    )
    parser.add_argument(
        "--log-prompts",
        action="store_true",
        default=False,
        help="Log full message list sent to the model at each step (JSONL in results/)",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        default=False,
        help="Save session directly to results/published/ instead of results/",
    )
    args = parser.parse_args()
    # Normalise --model alias into args.models list
    if args._model_alias is not None:
        args.models = [args._model_alias]
    return args


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Run benchmark and save results.

    Returns:
        Exit code (0 for success, 1 for errors)
    """
    args = parse_arguments()

    # Determine tasks to run
    try:
        if args.fixture:
            candidate = TASKS_DIR / args.fixture
            if candidate.exists() and (candidate / "validation_spec.json").exists():
                fixtures = [candidate]
            else:
                console.print(f"[red]✗ Task not found: '{args.fixture}'[/red]")
                try:
                    available = discover_fixtures(TASKS_DIR)
                    console.print("[yellow]  Available tasks:[/yellow]")
                    for f in available:
                        console.print(f"[yellow]    - {f.name}[/yellow]")
                except FileNotFoundError:
                    pass
                return 1
        else:
            fixtures = discover_fixtures(TASKS_DIR)
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        return 1

    # Determine output base directory
    output_base = Path("results/published") if args.publish else OUTPUT_DIR

    # Create session directory (always, even for a single model)
    session_dir = output_base / _make_session_dir(args.session_name).name
    session_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[dim]Session: {session_dir}[/dim]")

    had_errors = False

    for model in args.models:
        model_safe = model.replace(":", "__")
        model_dir = session_dir / model_safe
        model_dir.mkdir(parents=True, exist_ok=True)

        show_header(model, fixtures, args.runs)

        all_results: List[BenchmarkResult] = []

        for index, fixture_path in enumerate(fixtures, start=1):
            show_fixture_header(fixture_path.name, index, len(fixtures))

            try:
                runner_module = _get_runner_module(fixture_path)
            except ValueError as e:
                console.print(f"[red]✗ {e}[/red]")
                had_errors = True
                continue

            # Pre-create output folder for agent tests so prompt_log_path is co-located.
            is_agent = hasattr(runner_module, "AgentTest")
            agent_out_dir: Optional[Path] = None
            if is_agent:
                unix_ts = int(time.time())
                agent_out_dir = (
                    model_dir
                    / f"{model_safe}__{fixture_path.name}__{args.runs}runs__{unix_ts}"
                )
                agent_out_dir.mkdir(parents=True, exist_ok=True)

            results = run_fixture(
                model,
                fixture_path,
                args.runs,
                runner_module,
                log_prompts=args.log_prompts,
                agent_output_dir=agent_out_dir,
                output_base=output_base,
            )

            if results is None:
                had_errors = True
                continue

            output_file = save_results(
                results,
                model,
                fixture_path.name,
                requested_runs=args.runs,
                agent_output_dir=agent_out_dir,
                output_dir=model_dir,
            )
            console.print(f"\n[green]✓ Results saved to {output_file}[/green]")

            show_fixture_summary(results, fixture_path.name)
            all_results.extend(results)

        if len(fixtures) > 1 and all_results:
            show_overall_summary(all_results, len(fixtures))

    return 1 if had_errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Benchmark interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]✗ Unexpected error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
