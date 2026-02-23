"""Refactoring test orchestrator for LLM benchmark.

This module orchestrates the refactoring test workflow:
1. Load fixture (prompt, validation spec, target project)
2. Call LLM
3. Validate output (compilation + AST + naming)
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
from src.refactoring.simple_component import validator
from src.refactoring.simple_component.validator import ASTResult, NamingResult

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Complete test execution result.

    Attributes:
        model: LLM model name (e.g., "qwen2.5-coder:7b-instruct-q8_0")
        fixture: Fixture name (e.g., "simple-component")
        timestamp: ISO 8601 timestamp of test execution
        run_number: Test run number (for multiple runs)
        compiles: True if TypeScript compilation succeeded
        compilation_errors: List of TypeScript compilation errors
        compilation_warnings: List of TypeScript compilation warnings
        pattern_score: AST pattern matching score (0.0-10.0)
        ast_missing: List of AST structures not found (e.g. ["interfaces", "script_lang"])
        naming_score: Naming convention score (0.0-10.0)
        naming_violations: List of naming convention violations found
        final_score: Weighted final score (0.0-10.0)
        scoring_weights: Weights used for final_score {"compilation": 0.5, ...}
        tokens_per_sec: LLM generation speed (tokens/second)
        duration_sec: Total test duration in seconds
        output_code: Generated Vue component code
        errors: List of test execution errors
    """

    model: str
    fixture: str
    timestamp: str
    run_number: int

    compiles: bool
    compilation_errors: List[str]
    compilation_warnings: List[str]
    pattern_score: float
    ast_missing: List[str]
    naming_score: float
    naming_violations: List[str]
    final_score: float
    scoring_weights: dict

    tokens_per_sec: float
    duration_sec: float

    output_code: str
    errors: List[str]


class RefactoringTest:
    """Phase 1: Prompt-only refactoring test orchestrator.

    Orchestrates the complete refactoring test workflow:
    - Loads fixture files (prompt, validation spec, target project)
    - Calls LLM
    - Validates output (compilation + AST + naming)
    - Calculates weighted final score
    - Returns structured BenchmarkResult

    Example:
        >>> test = RefactoringTest(
        ...     model="qwen2.5-coder:7b-instruct-q8_0",
        ...     fixture_path=Path("fixtures/refactoring/simple-component")
        ... )
        >>> result = test.run(run_number=1)
        >>> print(f"Score: {result.final_score}/10")
    """

    def __init__(self, model: str, fixture_path: Path):
        """Initialize test with model and fixture.

        Args:
            model: Ollama model name
            fixture_path: Path to fixture directory

        Raises:
            FileNotFoundError: If required fixture files missing
        """
        self.model = model
        self.fixture_path = fixture_path
        self.fixture_name = fixture_path.name

        logger.info(f"Initializing RefactoringTest: model={model}, fixture={self.fixture_name}")

        # Load prompt template
        prompt_file = fixture_path / "prompt.md"
        if not prompt_file.exists():
            raise FileNotFoundError(f"prompt.md not found in {fixture_path}")
        self.prompt_template = prompt_file.read_text()

        # Load validation spec
        spec_file = fixture_path / "validation_spec.json"
        if not spec_file.exists():
            raise FileNotFoundError(f"validation_spec.json not found in {fixture_path}")
        with open(spec_file) as f:
            self.validation_spec = json.load(f)

        # Locate target project
        self.target_project = fixture_path / "target_project"
        if not self.target_project.exists():
            raise FileNotFoundError(f"target_project not found in {fixture_path}")

        # Locate target file
        target_file_rel = self.validation_spec["target_file"]
        self.target_file = self.target_project / target_file_rel

        if not self.target_file.exists():
            raise FileNotFoundError(
                f"Target file {target_file_rel} not found in target_project"
            )

        # Store original code (for restoration after test)
        self.original_code = self.target_file.read_text()

        logger.info(
            f"Fixture loaded: prompt={len(self.prompt_template)} chars, "
            f"target_file={target_file_rel}, "
            f"original_code={len(self.original_code)} chars"
        )

    def run(self, run_number: int = 1) -> BenchmarkResult:
        """Execute single test run (Phase 1 prompt-only workflow).

        Workflow:
        1. Restore original file
        2. Render prompt with {{original_code}}
        3. Call LLM
        4. Extract code from response
        5. Write output to target file
        6. Validate compilation (vue-tsc)
        7. Validate AST patterns
        8. Validate naming conventions
        9. Calculate final score (weighted)
        10. Cleanup (restore original file)
        11. Return BenchmarkResult

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

            # 2. Render prompt
            rendered_prompt = self.prompt_template.replace("{{original_code}}", self.original_code)
            logger.info(f"Rendered prompt: {len(rendered_prompt)} chars")

            # 3. Call LLM
            chat_result = ollama_client.chat(model=self.model, prompt=rendered_prompt)

            logger.info(
                f"LLM response: {chat_result.tokens_per_sec:.1f} tok/s, "
                f"{chat_result.duration_sec:.2f}s"
            )

            # 4. Extract code from response (handle markdown fences)
            output_code = self._extract_vue_code(chat_result.response_text)

            # 5. Write output to target file
            self.target_file.write_text(output_code)
            logger.info(f"Wrote LLM output to {self.target_file}")

            # 6. Validate compilation
            compilation_result = validator.validate_compilation(self.target_project)
            logger.info(f"Compilation: {compilation_result.success}")

            # 7. Validate AST patterns
            try:
                ast_result = validator.validate_ast_structure(
                    output_code,
                    self.validation_spec.get("required_patterns", {})
                )
                logger.info(f"AST score: {ast_result.score}/10")
            except Exception as e:
                logger.warning(f"AST validation failed: {e}")
                errors.append(f"AST validation error: {e}")
                ast_result = ASTResult(
                    has_interfaces=False,
                    has_type_annotations=False,
                    has_imports=False,
                    missing=["AST parsing failed"],
                    score=0.0,
                )

            # 8. Validate naming
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

            # 9. Calculate final score (weighted)
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
                naming_score=naming_result.score * 10,  # Scale to 0-10
                naming_violations=naming_result.violations,
                final_score=final_score,
                scoring_weights=weights,
                tokens_per_sec=chat_result.tokens_per_sec,
                duration_sec=chat_result.duration_sec,
                output_code=output_code,
                errors=errors,
            )

        finally:
            # 10. Cleanup - restore original file
            self.target_file.write_text(self.original_code)
            logger.info("Restored original file (cleanup)")

    def _extract_vue_code(self, response: str) -> str:
        """Extract Vue code from LLM response (handle markdown fences).

        Args:
            response: Raw LLM response text

        Returns:
            Clean Vue SFC code without markdown fences
        """
        # Try to extract code from markdown fence
        vue_fence_pattern = r"```vue\s*\n(.*?)\n```"
        match = re.search(vue_fence_pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try generic code fence
        code_fence_pattern = r"```\s*\n(.*?)\n```"
        match = re.search(code_fence_pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # No fences - return as-is
        return response.strip()
