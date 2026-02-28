"""Creation test orchestrator for veevalidate-zod-form fixture.

Orchestrates the creation test workflow:
1. Load fixture (prompt, validation spec, target project)
2. Call LLM
3. Validate output (compilation + pattern + naming)
4. Calculate weighted score
5. Return structured result
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from src.common import ollama_client
from src.creation.veevalidate_zod_form import validator
from src.creation.veevalidate_zod_form.validator import ASTResult, NamingResult

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Complete test execution result."""

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
    """Creation test orchestrator for veevalidate-zod-form fixture.

    The prompt does not include {{original_code}} — the LLM creates
    the component from scratch based on the prompt instructions alone.
    """

    def __init__(self, model: str, fixture_path: Path):
        """Initialize test with model and fixture.

        Args:
            model: Ollama model name
            fixture_path: Path to fixture directory

        Raises:
            FileNotFoundError: If required fixture files are missing
        """
        self.model = model
        self.fixture_path = fixture_path
        self.fixture_name = fixture_path.name

        logger.info(f"Initializing CreationTest: model={model}, fixture={self.fixture_name}")

        prompt_file = fixture_path / "prompt.md"
        if not prompt_file.exists():
            raise FileNotFoundError(f"prompt.md not found in {fixture_path}")
        self.prompt_template = prompt_file.read_text()

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
                f"Target file {target_file_rel} not found in target_project"
            )

        self.original_code = self.target_file.read_text()

        logger.info(
            f"Fixture loaded: prompt={len(self.prompt_template)} chars, "
            f"target_file={target_file_rel}"
        )

    def run(self, run_number: int = 1) -> BenchmarkResult:
        """Execute single test run.

        Workflow:
        1. Restore original (empty) file
        2. Call LLM with prompt (no {{original_code}} substitution)
        3. Extract code from response
        4. Write output to target file
        5. Validate compilation (vue-tsc)
        6. Validate patterns (regex)
        7. Validate naming conventions
        8. Calculate final score (weighted)
        9. Cleanup (restore original file)
        10. Return BenchmarkResult

        Args:
            run_number: Test run number (for multiple runs)

        Returns:
            BenchmarkResult with all metrics and validation results
        """
        timestamp = datetime.now().isoformat()
        errors = []

        try:
            # 1. Restore original file
            self.target_file.write_text(self.original_code)
            logger.info(f"Restored original file: {self.target_file}")

            # 2. Call LLM (prompt used as-is — no template substitution)
            chat_result = ollama_client.chat(model=self.model, prompt=self.prompt_template)
            logger.info(
                f"LLM response: {chat_result.tokens_per_sec:.1f} tok/s, "
                f"{chat_result.duration_sec:.2f}s"
            )

            # 3. Extract code from response
            output_code = self._extract_vue_code(chat_result.response_text)

            # 4. Write output to target file
            self.target_file.write_text(output_code)
            logger.info(f"Wrote LLM output to {self.target_file}")

            # 5. Validate compilation
            compilation_result = validator.validate_compilation(self.target_project)
            logger.info(f"Compilation: {compilation_result.success}")

            # 6. Validate patterns
            try:
                ast_result = validator.validate_ast_structure(
                    output_code,
                    self.validation_spec.get("required_patterns", {})
                )
                logger.info(f"AST score: {ast_result.score}/10")
            except Exception as e:
                logger.warning(f"AST validation failed: {e}")
                errors.append(f"AST validation error: {e}")
                ast_result = ASTResult(score=0.0, missing=["AST parsing failed"])

            # 7. Validate naming
            try:
                naming_result = validator.validate_naming(
                    output_code,
                    self.validation_spec.get("naming_conventions", {})
                )
                logger.info(f"Naming score: {naming_result.score}")
            except Exception as e:
                logger.warning(f"Naming validation failed: {e}")
                errors.append(f"Naming validation error: {e}")
                naming_result = NamingResult(
                    follows_conventions=False,
                    violations=["Naming validation failed"],
                    score=0.0,
                )

            # 8. Calculate final score (weighted)
            weights = self.validation_spec["scoring"]
            final_score = (
                (1.0 if compilation_result.success else 0.0) * weights["compilation"] +
                (ast_result.score / 10.0) * weights["pattern_match"] +
                naming_result.score * weights["naming"]
            ) * 10

            logger.info(f"Final score: {final_score:.1f}/10")

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
                ast_checks=ast_result.checks,
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
            # 9. Cleanup - restore original file
            self.target_file.write_text(self.original_code)
            logger.info("Restored original file (cleanup)")

    def _extract_vue_code(self, response: str) -> str:
        """Extract Vue SFC code from LLM response (strip markdown fences if present)."""
        vue_fence_pattern = r"```vue\s*\n(.*?)\n```"
        match = re.search(vue_fence_pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()

        code_fence_pattern = r"```\s*\n(.*?)\n```"
        match = re.search(code_fence_pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()

        return response.strip()
