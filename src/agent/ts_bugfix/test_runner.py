"""Agent test orchestrator for ts-bugfix fixture.

Orchestrates the agent benchmark workflow:
1. Load fixture (prompt, validation spec, target project)
2. Restore target file to initial buggy state
3. Run smolagents ToolCallingAgent loop (read/write/compile tools)
4. Validate final state of target file (compilation + AST + naming)
5. Calculate weighted score
6. Cleanup (restore original buggy state)
7. Return AgentBenchmarkResult
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console

from src.agent.common.agent_client import run_agent
from src.agent.common.tools import make_tools
from src.agent.ts_bugfix import validator
from src.agent.ts_bugfix.validator import ASTResult, NamingResult

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class AgentBenchmarkResult:
    """Complete agent test execution result.

    Superset of BenchmarkResult, extended with agent-specific metrics.
    Compatible with run_test.py's show_fixture_summary() and save_results()
    (all accessed fields are present; tokens_per_sec may be 0.0 if model
    doesn't expose token counts via Ollama's /v1 endpoint).

    Attributes:
        iterations: Number of agent steps taken (one step = one LLM call).
        max_iterations: Configured ceiling for this fixture.
        succeeded: True if task completed before hitting max_iterations.
        tool_call_log: Ordered list of {step, tool, args, result_summary}.
    """

    # ── shared with BenchmarkResult ──
    model: str
    fixture: str
    timestamp: str
    run_number: int

    compiles: bool
    compilation_errors: List[str]
    compilation_warnings: List[str]
    pattern_score: float
    ast_missing: List[str]
    ast_checks: dict
    naming_score: float
    naming_violations: List[str]
    final_score: float
    scoring_weights: dict

    tokens_per_sec: float
    duration_sec: float

    output_code: str
    errors: List[str]

    # ── agent-specific ──
    steps: int            # individual tool-calling LLM turns
    max_steps: int        # configured ceiling (max_steps in validation_spec.json)
    iterations: int       # number of run_compilation calls (= fix-and-verify cycles)
    succeeded: bool
    tool_call_log: List[Dict[str, Any]] = field(default_factory=list)


class AgentTest:
    """Agent benchmark test orchestrator for ts-bugfix fixture.

    Unlike RefactoringTest/CreationTest, the agent reads and writes files
    itself via tools. AgentTest:
    - Restores the buggy state before each run
    - Provides tools to the agent
    - Runs the smolagents loop
    - Validates whatever the agent produced

    Compatible with run_test.py's run_fixture():
        runner_class(model=model, fixture_path=fixture_path)

    Example:
        >>> test = AgentTest(
        ...     model="qwen2.5-coder:7b-instruct-q8_0",
        ...     fixture_path=Path("fixtures/agent/ts-bugfix")
        ... )
        >>> result = test.run(run_number=1)
        >>> print(f"Score: {result.final_score}/10 in {result.iterations} steps")
    """

    def __init__(self, model: str, fixture_path: Path):
        """Initialize test with model and fixture.

        Reads max_iterations and allowed_write_paths from validation_spec.json.

        Args:
            model: Ollama model name (e.g. 'qwen2.5-coder:7b-instruct-q8_0').
            fixture_path: Path to fixture directory.

        Raises:
            FileNotFoundError: If prompt.md, validation_spec.json, target_project,
                               or the target file are missing.
        """
        self.model = model
        self.fixture_path = fixture_path
        self.fixture_name = fixture_path.name

        prompt_file = fixture_path / "prompt.md"
        if not prompt_file.exists():
            raise FileNotFoundError(f"prompt.md not found in {fixture_path}")
        self.prompt = prompt_file.read_text()

        spec_file = fixture_path / "validation_spec.json"
        if not spec_file.exists():
            raise FileNotFoundError(f"validation_spec.json not found in {fixture_path}")
        with open(spec_file) as f:
            self.validation_spec = json.load(f)

        self.target_project = fixture_path / "target_project"
        if not self.target_project.exists():
            raise FileNotFoundError(f"target_project not found in {fixture_path}")

        target_file_rel = self.validation_spec["target_file"]
        self.target_file = self.target_project / target_file_rel
        if not self.target_file.exists():
            raise FileNotFoundError(
                f"Target file '{target_file_rel}' not found in {self.target_project}"
            )

        # The "original" state IS the buggy state — the fixture ships broken
        self.original_code = self.target_file.read_text()

        self.max_steps = self.validation_spec.get(
            "max_steps", self.validation_spec.get("max_iterations", 5)
        )
        self.allowed_paths: List[str] = self.validation_spec.get(
            "allowed_write_paths", [target_file_rel]
        )

    def run(self, run_number: int = 1) -> AgentBenchmarkResult:
        """Execute a single agent test run.

        Workflow:
        1. Restore target file to original buggy state
        2. Build tools bound to this target_project
        3. Run agent loop
        4. Read final state of target file
        5. Validate compilation + AST + naming
        6. Calculate weighted score
        7. Restore original buggy state (in finally)
        8. Return AgentBenchmarkResult

        Args:
            run_number: Run index (1-based).
        """
        timestamp = datetime.now().isoformat()
        errors: List[str] = []

        try:
            # 1. Restore buggy state
            self.target_file.write_text(self.original_code)

            # 2. Build tools
            tools = make_tools(self.target_project, self.allowed_paths)

            # 3. Run agent
            agent_result = run_agent(
                model=self.model,
                task=self.prompt,
                tools=tools,
                max_steps=self.max_steps,
            )
            errors.extend(agent_result.errors)
            iterations = sum(
                1 for e in agent_result.tool_call_log if e.get("tool") == "run_compilation"
            )

            # 4. Read final file state
            output_code = ""
            try:
                output_code = self.target_file.read_text()
            except Exception as e:
                errors.append(f"Could not read target file after agent run: {e}")

            # 5a. Validate compilation
            compilation_result = validator.validate_compilation(self.target_project)

            # 5b. Validate AST patterns
            ast_result: ASTResult
            try:
                ast_result = validator.validate_ast_structure(
                    output_code,
                    self.validation_spec.get("required_patterns", {}),
                )
            except Exception as e:
                errors.append(f"AST validation error: {e}")
                ast_result = ASTResult(
                    has_interfaces=False,
                    has_type_annotations=False,
                    has_imports=False,
                    missing=["AST parsing failed"],
                    score=0.0,
                )

            # 5c. Validate naming
            naming_result: NamingResult
            try:
                naming_result = validator.validate_naming(
                    output_code,
                    self.validation_spec.get("naming_conventions", {}),
                )
            except Exception as e:
                errors.append(f"Naming validation error: {e}")
                naming_result = NamingResult(
                    follows_conventions=False,
                    violations=["Naming validation failed"],
                    score=0.0,
                )

            # 6. Calculate final score
            weights = self.validation_spec["scoring"]
            final_score = (
                (1.0 if compilation_result.success else 0.0) * weights["compilation"]
                + (ast_result.score / 10.0) * weights["pattern_match"]
                + naming_result.score * weights["naming"]
            ) * 10

            return AgentBenchmarkResult(
                model=self.model,
                fixture=self.fixture_name,
                timestamp=timestamp,
                run_number=run_number,
                compiles=compilation_result.success,
                compilation_errors=compilation_result.errors,
                compilation_warnings=compilation_result.warnings,
                pattern_score=ast_result.score,
                ast_missing=ast_result.missing,
                ast_checks=ast_result.checks or {},
                naming_score=naming_result.score * 10,
                naming_violations=naming_result.violations,
                final_score=final_score,
                scoring_weights=weights,
                tokens_per_sec=agent_result.tokens_per_sec,
                duration_sec=agent_result.duration_sec,
                output_code=output_code,
                errors=errors,
                steps=agent_result.steps,
                max_steps=self.max_steps,
                iterations=iterations,
                succeeded=agent_result.succeeded,
                tool_call_log=agent_result.tool_call_log,
            )

        finally:
            # 7. Always restore original buggy state
            self.target_file.write_text(self.original_code)


def format_run(result: AgentBenchmarkResult) -> None:
    """Print a single agent run summary to the console."""
    compile_icon = "[green]✓[/green]" if result.compiles else "[red]✗[/red]"
    score_color = "green" if result.final_score >= 8.0 else "yellow" if result.final_score >= 5.0 else "red"
    success_icon = "[green]✓[/green]" if result.succeeded else "[yellow]~[/yellow]"

    w = result.scoring_weights
    compile_pts = (1.0 if result.compiles else 0.0) * w["compilation"] * 10
    pattern_pts = (result.pattern_score / 10.0) * w["pattern_match"] * 10
    naming_pts = (result.naming_score / 10.0) * w["naming"] * 10

    speed_str = f"{result.tokens_per_sec:.1f} tok/s" if result.tokens_per_sec > 0 else "N/A tok/s"

    console.print(
        f"{compile_icon} Compile  |  "
        f"[bold {score_color}]{result.final_score:.1f}/10[/bold {score_color}]  "
        f"[dim]{result.duration_sec:.1f}s  {speed_str}[/dim]  "
        f"{success_icon} {result.steps}/{result.max_steps} steps | {result.iterations} compile checks"
    )
    console.print(
        f"   Scoring:  "
        f"compile {compile_pts:.1f}pt ({w['compilation']*100:.0f}%) + "
        f"pattern {pattern_pts:.1f}pt ({w['pattern_match']*100:.0f}%) + "
        f"naming {naming_pts:.1f}pt ({w['naming']*100:.0f}%)"
    )

    # Tool call trace
    for entry in result.tool_call_log:
        args_str = str(entry.get("args", {}))[:60]
        summary = entry.get("result_summary", "")[:80]
        console.print(
            f"   [dim]step {entry['step']}: {entry['tool']}({args_str}) → {summary}[/dim]"
        )

    if result.ast_checks:
        icons = {True: "[green]✓[/green]", False: "[red]✗[/red]"}
        for check_name, passed in result.ast_checks.items():
            console.print(f"   {icons[passed]} {check_name}")

    if result.compilation_errors:
        for err in result.compilation_errors[:3]:
            console.print(f"   [red]  TS error: {err}[/red]")

    if result.errors:
        for err in result.errors[:3]:
            console.print(f"   [red]  ⚠ {err[:120]}[/red]")

    console.print("[dim]──────────[/dim]\n")
