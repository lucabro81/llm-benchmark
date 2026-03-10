"""Agent test orchestrator for the nuxt-form-agent-twofiles fixture.

Differences from nuxt-form-agent-guided (Test B):
- The model writes TWO files in order:
    1. apps/web/src/registration/types/index.ts  (Zod schema + TS types)
    2. apps/web/src/registration/components/RegistrationForm.vue  (imports from types)
- output_code in result contains both files combined (Vue + separator + types)
  so format_run() shows the complete generated output.
- max_steps: 15 (vs 10 for guided — extra steps for the two-file write cycle)
- Tools: ONLY write_file + run_compilation (no read_file, no list_files, no query_rag)
"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from smolagents import tool

from src.agent.common.agent_client import run_agent
from src.agent.nuxt_form_agent_twofiles import validator
from src.agent.nuxt_form_agent_twofiles.validator import ASTResult, NamingResult

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class AgentBenchmarkResult:
    """Complete agent test execution result for the nuxt-form-agent-twofiles fixture."""

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

    steps: int
    max_steps: int
    iterations: int
    succeeded: bool
    tool_call_log: List[Dict[str, Any]] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    first_compile_success_step: Optional[int] = None
    compile_error_recovery_count: int = 0
    rag_queries_count: int = 0
    read_file_count: int = 0
    list_files_count: int = 0


def _make_tools(
    target_project: Path,
    allowed_paths: List[str],
    compilation_cwd: Path,
    compilation_command: str,
) -> List:
    """Build tools for the twofiles fixture: ONLY write_file + run_compilation."""
    target_project = target_project.resolve()
    compilation_cwd = compilation_cwd.resolve()
    resolved_root = target_project
    allowed_write_set = set(allowed_paths)

    def _safe_resolve(relative_path: str) -> Path:
        full = (target_project / relative_path).resolve()
        full.relative_to(resolved_root)
        return full

    def _run_compile() -> str:
        try:
            result = subprocess.run(
                ["npm", "run", compilation_command],
                cwd=compilation_cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return "Compilation succeeded."
            combined = result.stdout + "\n" + result.stderr
            error_lines = [
                line.strip()
                for line in combined.split("\n")
                if "error TS" in line or " - error" in line
            ]
            return "\n".join(error_lines) if error_lines else combined.strip()
        except subprocess.TimeoutExpired:
            return "ERROR: Compilation timed out after 60 seconds."
        except Exception as e:
            return f"ERROR: {e}"

    @tool
    def write_file(path: str, content: str) -> str:
        """Write content to a file, then run TypeScript compilation automatically.

        Only paths in the fixture's allowed_write_paths may be written.

        Args:
            path: Relative path to write (e.g. 'apps/web/src/registration/types/index.ts').
            content: Complete file content to write.

        Returns:
            'File written.\\nCompilation succeeded.' on success,
            'File written.\\nCompilation errors:\\n{errors}' if TS errors remain,
            or an error message starting with 'ERROR:' if the write failed.
        """
        if path not in allowed_write_set:
            return (
                f"ERROR: Writing to '{path}' is not permitted. "
                f"Allowed: {sorted(allowed_write_set)}"
            )
        try:
            full = _safe_resolve(path)
            full.parent.mkdir(parents=True, exist_ok=True)
            content = content.replace("\\n", "\n").replace("\\t", "\t")
            full.write_text(content)
        except ValueError:
            return f"ERROR: Path '{path}' is outside the project directory."
        except Exception as e:
            return f"ERROR: {e}"

        compile_result = _run_compile()
        if compile_result == "Compilation succeeded.":
            return f"File written.\n{compile_result}"
        return f"File written.\nCompilation errors:\n{compile_result}"

    @tool
    def run_compilation() -> str:
        """Run TypeScript compilation and return errors.

        Returns:
            'Compilation succeeded.' if clean, otherwise the TypeScript error lines.
        """
        return _run_compile()

    return [write_file, run_compilation]


class AgentTest:
    """Agent benchmark test for the nuxt-form-agent-twofiles fixture.

    The model receives complete API docs in the prompt and must write two files:
    types/index.ts (schema + types) then RegistrationForm.vue (imports from types).
    Tests whether the model can handle a two-file dependency chain with TS feedback.
    """

    def __init__(self, model: str, fixture_path: Path, prompt_version: str | None = None):
        self.model = model
        self.fixture_path = fixture_path
        self.fixture_name = fixture_path.name

        prompt_filename = f"prompt-{prompt_version}.md" if prompt_version else "prompt.md"
        prompt_file = fixture_path / prompt_filename
        if not prompt_file.exists():
            raise FileNotFoundError(f"{prompt_filename} not found in {fixture_path}")
        self.prompt = prompt_file.read_text()

        spec_file = fixture_path / "validation_spec.json"
        if not spec_file.exists():
            raise FileNotFoundError(f"validation_spec.json not found in {fixture_path}")
        with open(spec_file) as f:
            self.validation_spec = json.load(f)

        tp_path_rel = self.validation_spec.get("target_project_path")
        if tp_path_rel:
            self.target_project = (fixture_path / tp_path_rel).resolve()
        else:
            self.target_project = fixture_path / "target_project"

        if not self.target_project.exists():
            raise FileNotFoundError(f"target_project not found: {self.target_project}")

        target_file_rel = self.validation_spec["target_file"]
        self.target_file = self.target_project / target_file_rel
        if not self.target_file.exists():
            raise FileNotFoundError(
                f"Target file '{target_file_rel}' not found in {self.target_project}"
            )
        self.original_code = self.target_file.read_text()

        types_rel = "apps/web/src/registration/types/index.ts"
        self._types_file = self.target_project / types_rel
        self.original_types = self._types_file.read_text() if self._types_file.exists() else ""

        self.max_steps = self.validation_spec.get("max_steps", 15)
        self.allowed_paths: List[str] = self.validation_spec.get(
            "allowed_write_paths", [target_file_rel]
        )

        compilation_cwd_rel = self.validation_spec.get("compilation_cwd", "apps/web")
        self._compilation_cwd = self.target_project / compilation_cwd_rel
        self._compilation_command = self.validation_spec.get("compilation_command", "check-types")

    def run(self, run_number: int = 1, prompt_log_path: "Optional[Path]" = None) -> AgentBenchmarkResult:
        """Execute a single agent test run."""
        timestamp = datetime.now().isoformat()
        errors: List[str] = []

        try:
            # 1. Restore stubs
            self.target_file.write_text(self.original_code)
            if self._types_file.exists() or self.original_types:
                self._types_file.write_text(self.original_types)

            # 2. Build tools
            tools = _make_tools(
                target_project=self.target_project,
                allowed_paths=self.allowed_paths,
                compilation_cwd=self._compilation_cwd,
                compilation_command=self._compilation_command,
            )

            # 3. Run agent
            agent_result = run_agent(
                model=self.model,
                task=self.prompt,
                tools=tools,
                max_steps=self.max_steps,
                prompt_log_path=prompt_log_path,
            )
            errors.extend(agent_result.errors)
            iterations = sum(
                1 for e in agent_result.tool_call_log
                if e.get("tool") in ("write_file", "run_compilation")
            )

            # 4. Read final state of both files
            vue_code = ""
            types_code = ""
            try:
                vue_code = self.target_file.read_text()
            except Exception as e:
                errors.append(f"Could not read target file after agent run: {e}")
            try:
                if self._types_file.exists():
                    types_code = self._types_file.read_text()
            except Exception:
                pass

            # Combine for validation and display
            output_code = vue_code
            if types_code:
                output_code = vue_code + "\n\n// --- types/index.ts ---\n" + types_code
            combined_code = output_code

            # 5a. Compile
            compilation_result = validator.validate_compilation(
                target_project=self.target_project,
                compilation_command=self._compilation_command,
                compilation_cwd=self._compilation_cwd,
            )

            # 5b. Pattern check
            ast_result: ASTResult
            try:
                ast_result = validator.validate_ast_structure(
                    combined_code,
                    self.validation_spec.get("required_patterns", {}),
                )
            except Exception as e:
                errors.append(f"AST validation error: {e}")
                ast_result = ASTResult(score=0.0, missing=["pattern validation failed"])

            # 5c. Naming check
            naming_result: NamingResult
            try:
                naming_result = validator.validate_naming(
                    combined_code,
                    self.validation_spec.get("naming_conventions", {}),
                )
            except Exception as e:
                errors.append(f"Naming validation error: {e}")
                naming_result = NamingResult(
                    follows_conventions=False,
                    violations=["Naming validation failed"],
                    score=0.0,
                )

            # 6. Score
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
                total_input_tokens=agent_result.total_input_tokens,
                total_output_tokens=agent_result.total_output_tokens,
                first_compile_success_step=agent_result.first_compile_success_step,
                compile_error_recovery_count=agent_result.compile_error_recovery_count,
                rag_queries_count=agent_result.rag_queries_count,
                read_file_count=agent_result.read_file_count,
                list_files_count=agent_result.list_files_count,
            )

        finally:
            # 7. Always restore stubs
            self.target_file.write_text(self.original_code)
            if self._types_file.exists() or self.original_types:
                self._types_file.write_text(self.original_types)


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

    for entry in result.tool_call_log:
        args_str = str(entry.get("args", {}))[:60]
        summary = entry.get("result_summary", "")[:80]
        console.print(f"   [dim]step {entry['step']}: {entry['tool']}({args_str}) → {summary}[/dim]")

    if result.ast_checks:
        icons = {True: "[green]✓[/green]", False: "[red]✗[/red]"}
        for check_name, passed in result.ast_checks.items():
            console.print(f"   {icons[bool(passed)]} {check_name}")

    if result.compilation_errors:
        for err in result.compilation_errors[:3]:
            console.print(f"   [red]  TS error: {err}[/red]")

    if result.errors:
        for err in result.errors[:3]:
            console.print(f"   [red]  ⚠ {err[:120]}[/red]")

    if result.output_code:
        lines = result.output_code.splitlines()
        console.print(f"[dim]--- Generated code ({len(lines)} lines) ---[/dim]")
        console.print(f"[dim]{result.output_code}[/dim]")

    console.print("[dim]──────────[/dim]\n")
