#!/usr/bin/env python3
"""CLI runner for LLM benchmark - Phase 1 (Prompt-Only Baseline).

Usage:
    python run_test.py --model <model> [--fixture <name>] [--runs <n>]

Arguments:
    --model    (required) Ollama model name (e.g., qwen2.5-coder:7b-instruct-q8_0)
    --fixture  (optional) Fixture name under fixtures/refactoring/. Runs ALL if omitted.
    --runs     (optional) Number of runs per fixture (default: 3)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Type

from rich.console import Console

from src.refactoring.simple_component.test_runner import BenchmarkResult

OUTPUT_DIR = Path("results")
FIXTURES_BASE = Path("fixtures/refactoring")
FIXTURES_CREATION = Path("fixtures/creation")

# Explicit mapping: fixture directory name → test runner module path
_RUNNER_MAP = {
    "simple-component": "src.refactoring.simple_component.test_runner",
    "typed-emits-composable": "src.refactoring.typed_emits_composable.test_runner",
    "veevalidate-zod-form": "src.creation.veevalidate_zod_form.test_runner",
}

console = Console()


# ---------------------------------------------------------------------------
# Fixture discovery
# ---------------------------------------------------------------------------

def discover_fixtures(base_dir: Path = FIXTURES_BASE) -> List[Path]:
    """Return sorted list of valid fixture paths in base_dir.

    A valid fixture must contain a validation_spec.json file.

    Args:
        base_dir: Directory to search for fixtures

    Returns:
        Sorted list of fixture Paths

    Raises:
        FileNotFoundError: If base_dir does not exist or contains no valid fixtures
    """
    if not base_dir.exists():
        raise FileNotFoundError(f"Fixtures directory not found: {base_dir}")

    fixtures = sorted(
        [p for p in base_dir.iterdir() if p.is_dir() and (p / "validation_spec.json").exists()],
        key=lambda p: p.name,
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
    if hasattr(module, "RefactoringTest"):
        return module.RefactoringTest
    return module.CreationTest


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def show_header(model: str, fixtures: List[Path], runs: int):
    """Display benchmark header."""
    fixture_names = ", ".join(f.name for f in fixtures)
    console.print("\n[bold cyan]╔════════════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║  LLM Benchmark - Phase 1 (Prompt-Only)     ║[/bold cyan]")
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

def save_results(results: List[BenchmarkResult], model: str, fixture_name: str) -> Path:
    """Save results for one fixture to a JSON file.

    Args:
        results: List of BenchmarkResult for all runs of this fixture
        model: Model name (used in filename)
        fixture_name: Fixture name (used in filename)

    Returns:
        Path to saved JSON file
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = results[0].timestamp.replace(":", "-")
    model_safe = model.replace(":", "_").replace(".", "-")
    output_file = OUTPUT_DIR / f"{model_safe}_{fixture_name}_{timestamp}.json"
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
) -> Optional[List[BenchmarkResult]]:
    """Run benchmark for a single fixture.

    Args:
        model: Ollama model name
        fixture_path: Path to fixture directory
        runs: Number of runs to execute
        runner_module: Imported runner module (exposes test class and format_run)

    Returns:
        List of BenchmarkResult, or None if fixture failed to load
    """
    runner_class = _get_runner_class(runner_module)
    try:
        test = runner_class(model=model, fixture_path=fixture_path)
    except FileNotFoundError as e:
        console.print(f"[red]✗ Error loading fixture '{fixture_path.name}': {e}[/red]")
        console.print("[yellow]  → Skipping this fixture[/yellow]")
        return None

    results = []
    for i in range(runs):
        console.print(f"[dim]── Run {i + 1}/{runs} ──[/dim]")
        result = test.run(run_number=i + 1)
        results.append(result)
        runner_module.format_run(result)

    return results


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="LLM Benchmark - Phase 1 (Prompt-Only Baseline)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_test.py --model qwen2.5-coder:7b-instruct-q8_0\n"
            "  python run_test.py --model qwen2.5-coder:7b-instruct-q8_0 --fixture simple-component\n"
            "  python run_test.py --model qwen2.5-coder:7b-instruct-q8_0 --runs 1\n"
        ),
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Ollama model name (e.g., qwen2.5-coder:7b-instruct-q8_0)",
    )
    parser.add_argument(
        "--fixture",
        default=None,
        metavar="NAME",
        help="Fixture name under fixtures/refactoring/ (runs ALL if omitted)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        metavar="N",
        help="Number of runs per fixture (default: 3)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Run benchmark and save results.

    Returns:
        Exit code (0 for success, 1 for errors)
    """
    args = parse_arguments()

    # Determine fixtures to run
    try:
        if args.fixture:
            # Search in both fixtures/refactoring/ and fixtures/creation/
            fixture_path = None
            for base in (FIXTURES_BASE, FIXTURES_CREATION):
                candidate = base / args.fixture
                if candidate.exists() and (candidate / "validation_spec.json").exists():
                    fixture_path = candidate
                    break
            if fixture_path is None:
                console.print(f"[red]✗ Fixture not found: '{args.fixture}'[/red]")
                try:
                    available = discover_fixtures()
                    available += discover_fixtures(FIXTURES_CREATION)
                    console.print("[yellow]  Available fixtures:[/yellow]")
                    for f in available:
                        console.print(f"[yellow]    - {f.name}[/yellow]")
                except FileNotFoundError:
                    pass
                return 1
            fixtures = [fixture_path]
        else:
            fixtures = discover_fixtures()
            try:
                fixtures += discover_fixtures(FIXTURES_CREATION)
            except FileNotFoundError:
                pass
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        return 1

    show_header(args.model, fixtures, args.runs)

    all_results: List[BenchmarkResult] = []
    had_errors = False

    for index, fixture_path in enumerate(fixtures, start=1):
        show_fixture_header(fixture_path.name, index, len(fixtures))

        try:
            runner_module = _get_runner_module(fixture_path)
        except ValueError as e:
            console.print(f"[red]✗ {e}[/red]")
            had_errors = True
            continue

        results = run_fixture(args.model, fixture_path, args.runs, runner_module)

        if results is None:
            had_errors = True
            continue

        output_file = save_results(results, args.model, fixture_path.name)
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
