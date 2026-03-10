"""Creation test orchestrator for the nuxt-form-creation fixture.

Differences from the standard CreationTest:
- target_project resolved via target_project_path in validation_spec.json (relative to fixture dir)
  so it can point to the shared monorepo used by all nuxt-form fixtures
- Compilation uses compilation_cwd + compilation_command (npm run check-types from apps/web)
- types/index.ts state saved/restored defensively (shared target_project may be in use)
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from rich.console import Console

from src.common import ollama_client
from src.creation.nuxt_form_oneshot import validator
from src.creation.nuxt_form_oneshot.validator import ASTResult, NamingResult

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class BenchmarkResult:
    """Complete test execution result for the nuxt-form-creation fixture."""

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


class CreationTest:
    """Single-shot creation test for the nuxt-form-creation fixture.

    The model receives the complete component API docs inline in the prompt
    and must output a single RegistrationForm.vue with types defined inline.
    """

    def __init__(self, model: str, fixture_path: Path, prompt_version: str | None = None):
        self.model = model
        self.fixture_path = fixture_path
        self.fixture_name = fixture_path.name

        prompt_filename = f"prompt-{prompt_version}.md" if prompt_version else "prompt.md"
        prompt_file = fixture_path / prompt_filename
        if not prompt_file.exists():
            raise FileNotFoundError(f"{prompt_filename} not found in {fixture_path}")
        self.prompt_template = prompt_file.read_text()

        spec_file = fixture_path / "validation_spec.json"
        if not spec_file.exists():
            raise FileNotFoundError(f"validation_spec.json not found in {fixture_path}")
        with open(spec_file) as f:
            self.validation_spec = json.load(f)

        # Resolve target_project: honour target_project_path override, fall back to local
        tp_path_rel = self.validation_spec.get("target_project_path")
        if tp_path_rel:
            self.target_project = (fixture_path / tp_path_rel).resolve()
        else:
            self.target_project = fixture_path / "target_project"

        if not self.target_project.exists():
            raise FileNotFoundError(f"target_project not found: {self.target_project}")

        # Compilation config (monorepo: run check-types from apps/web)
        compilation_cwd_rel = self.validation_spec.get("compilation_cwd", ".")
        self._compilation_cwd = self.target_project / compilation_cwd_rel
        self._compilation_command = self.validation_spec.get("compilation_command", "type-check")

        target_file_rel = self.validation_spec["target_file"]
        self.target_file = self.target_project / target_file_rel
        if not self.target_file.exists():
            raise FileNotFoundError(
                f"Target file '{target_file_rel}' not found in {self.target_project}"
            )
        self.original_code = self.target_file.read_text()

        # Also save types/index.ts state (defensive: shared target_project)
        types_rel = "apps/web/src/registration/types/index.ts"
        self._types_file = self.target_project / types_rel
        self.original_types = self._types_file.read_text() if self._types_file.exists() else ""

    def run(self, run_number: int = 1) -> BenchmarkResult:
        """Execute single test run.

        Workflow:
        1. Restore original (empty) stub
        2. Call LLM with prompt (no template substitution)
        3. Extract .vue code from response
        4. Write to target file
        5. Validate compilation (npm run check-types from apps/web)
        6. Validate patterns (regex)
        7. Validate naming
        8. Calculate final score
        9. Restore stubs (always, in finally)
        """
        timestamp = datetime.now().isoformat()
        errors: List[str] = []

        try:
            # 1. Restore stub
            self.target_file.write_text(self.original_code)

            # 2. Call LLM
            chat_result = ollama_client.chat(model=self.model, prompt=self.prompt_template)

            # 3. Extract .vue code
            output_code = self._extract_vue_code(chat_result.response_text)

            # 4. Write output
            self.target_file.write_text(output_code)

            # 5. Compile
            compilation_result = validator.validate_compilation(
                target_project=self.target_project,
                compilation_command=self._compilation_command,
                compilation_cwd=self._compilation_cwd,
            )

            # 6. Pattern check
            try:
                ast_result = validator.validate_ast_structure(
                    output_code,
                    self.validation_spec.get("required_patterns", {}),
                )
            except Exception as e:
                errors.append(f"AST validation error: {e}")
                ast_result = ASTResult(score=0.0, missing=["pattern validation failed"])

            # 7. Naming check
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

            # 8. Score
            weights = self.validation_spec["scoring"]
            final_score = (
                (1.0 if compilation_result.success else 0.0) * weights["compilation"]
                + (ast_result.score / 10.0) * weights["pattern_match"]
                + naming_result.score * weights["naming"]
            ) * 10

            return BenchmarkResult(
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
                tokens_per_sec=chat_result.tokens_per_sec,
                duration_sec=chat_result.duration_sec,
                output_code=output_code,
                errors=errors,
            )

        finally:
            # 9. Always restore stubs
            self.target_file.write_text(self.original_code)
            if self._types_file.exists() or self.original_types:
                self._types_file.write_text(self.original_types)

    def _extract_vue_code(self, response: str) -> str:
        """Extract Vue SFC code from LLM response (strip markdown fences if present)."""
        vue_fence = r"```vue\s*\n(.*?)\n```"
        match = re.search(vue_fence, response, re.DOTALL)
        if match:
            return match.group(1).strip()

        code_fence = r"```\s*\n(.*?)\n```"
        match = re.search(code_fence, response, re.DOTALL)
        if match:
            return match.group(1).strip()

        return response.strip()


def format_run(result: BenchmarkResult) -> None:
    """Print a single run summary to the console."""
    compile_icon = "[green]✓[/green]" if result.compiles else "[red]✗[/red]"
    score_color = "green" if result.final_score >= 8.0 else "yellow" if result.final_score >= 5.0 else "red"

    w = result.scoring_weights
    compile_pts = (1.0 if result.compiles else 0.0) * w["compilation"] * 10
    pattern_pts = (result.pattern_score / 10.0) * w["pattern_match"] * 10
    naming_pts = (result.naming_score / 10.0) * w["naming"] * 10

    speed_str = f"{result.tokens_per_sec:.1f} tok/s" if result.tokens_per_sec > 0 else "N/A tok/s"

    console.print(
        f"{compile_icon} Compile  |  "
        f"[bold {score_color}]{result.final_score:.1f}/10[/bold {score_color}]  "
        f"[dim]{result.duration_sec:.1f}s  {speed_str}[/dim]"
    )
    console.print(
        f"   Scoring:  "
        f"compile {compile_pts:.1f}pt ({w['compilation']*100:.0f}%) + "
        f"pattern {pattern_pts:.1f}pt ({w['pattern_match']*100:.0f}%) + "
        f"naming {naming_pts:.1f}pt ({w['naming']*100:.0f}%)"
    )

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
