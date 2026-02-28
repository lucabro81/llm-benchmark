"""Regex-based validation for the veevalidate-zod-form creation fixture.

Unlike the refactoring fixtures, this validator does not invoke parse_vue_ast.js
because the patterns to check (useForm calls, z.object schema, field presence,
error display) are not TypeScript type-level constructs — they are runtime
patterns that regex detects more directly and reliably.

Scoring breakdown (validate_ast_structure, 0-10):
  +2  has_script_lang_ts
  +2  has_use_form
  +2  has_zod_schema  (z.object + toTypedSchema)
  +2  has_all_fields  (all required fields present)
  +2  has_error_display  (errors. or <ErrorMessage)
"""

import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class ASTResult:
    score: float
    missing: List[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)


@dataclass
class CompilationResult:
    success: bool
    errors: List[str]
    warnings: List[str]
    duration_sec: float


@dataclass
class NamingResult:
    follows_conventions: bool
    violations: List[str]
    score: float


def validate_ast_structure(code: str, expected_patterns: dict) -> ASTResult:
    """Validate component patterns using regex on raw component text.

    Checks:
    - script_lang: <script ... lang="ts"> present
    - use_form: useForm( call present
    - zod_schema: z.object( AND toTypedSchema( both present
    - fields: all required field names present (via useField/defineField or v-model)
    - error_display: errors. or <ErrorMessage present

    Args:
        code: Raw Vue SFC source code
        expected_patterns: dict from validation_spec.json required_patterns

    Returns:
        ASTResult with score (0-10) and list of missing pattern keys
    """
    if not code:
        return ASTResult(score=0.0, missing=list(expected_patterns.keys()) if expected_patterns else [])

    missing = []
    score = 0.0
    checks = {}

    # --- script_lang ---
    if expected_patterns.get("script_lang") == "ts":
        found = bool(re.search(r"<script[^>]+lang=[\"']ts[\"']", code))
        checks["script_lang"] = found
        if found:
            score += 2.0
        else:
            missing.append("script_lang")
            logger.debug("Missing: script_lang")

    # --- use_form ---
    if "use_form" in expected_patterns:
        found = bool(re.search(r"\buseForm\s*\(", code))
        checks["use_form"] = found
        if found:
            score += 2.0
        else:
            missing.append("use_form")
            logger.debug("Missing: use_form")

    # --- zod_schema + typed_schema: treated as a single composite check (+2) ---
    # Both z.object( and toTypedSchema( must be present to earn the points.
    # If either key is listed in expected_patterns, we run this composite check.
    if "zod_schema" in expected_patterns or "typed_schema" in expected_patterns:
        has_z_object = bool(re.search(r"\bz\.object\s*\(", code))
        has_typed_schema = bool(re.search(r"\btoTypedSchema\s*\(", code))

        if "zod_schema" in expected_patterns:
            checks["zod_schema"] = has_z_object
        if "typed_schema" in expected_patterns:
            checks["typed_schema"] = has_typed_schema

        if has_z_object and has_typed_schema:
            score += 2.0
        else:
            if not has_z_object and "zod_schema" in expected_patterns:
                missing.append("zod_schema")
                logger.debug("Missing: zod_schema")
            if not has_typed_schema and "typed_schema" in expected_patterns:
                missing.append("typed_schema")
                logger.debug("Missing: typed_schema")

    # --- fields: all required field names must appear in the code ---
    required_fields: List[str] = expected_patterns.get("fields", [])
    if required_fields:
        missing_fields = [
            f for f in required_fields
            if not re.search(rf"\b{re.escape(f)}\b", code)
        ]
        checks["fields"] = missing_fields == []
        if not missing_fields:
            checks["fields_detail"] = {f: True for f in required_fields}
            score += 2.0
        else:
            checks["fields_detail"] = {f: f not in missing_fields for f in required_fields}
            missing.append("fields")
            logger.debug(f"Missing fields: {missing_fields}")

    # --- error_display: errors.field or <ErrorMessage ---
    if "error_display" in expected_patterns:
        has_errors_dot = bool(re.search(r"\berrors\.[a-zA-Z]", code))
        has_error_message_component = bool(re.search(r"<ErrorMessage", code))
        found = has_errors_dot or has_error_message_component
        checks["error_display"] = found
        if found:
            score += 2.0
        else:
            missing.append("error_display")
            logger.debug("Missing: error_display")

    logger.info(f"AST pattern score: {score}/10, missing: {missing}")
    return ASTResult(score=round(score, 1), missing=missing, checks=checks)


def validate_compilation(target_project: Path) -> CompilationResult:
    """Run vue-tsc in target project to validate TypeScript compilation.

    Args:
        target_project: Path to the Vue project root (contains package.json)

    Returns:
        CompilationResult with success flag, errors, warnings, duration
    """
    if not target_project.exists():
        raise FileNotFoundError(f"Target project not found: {target_project}")

    package_json = target_project / "package.json"
    if not package_json.exists():
        raise FileNotFoundError(f"package.json not found in {target_project}")

    logger.info(f"Running TypeScript compilation in {target_project}")

    start_time = time.time()
    try:
        result = subprocess.run(
            ["npm", "run", "type-check"],
            cwd=target_project,
            capture_output=True,
            text=True,
            timeout=30,
        )
        duration_sec = time.time() - start_time

        errors = []
        warnings = []

        # vue-tsc writes TS errors to stdout; check both streams
        for line in (result.stdout + "\n" + result.stderr).split("\n"):
            line = line.strip()
            if "error TS" in line or " - error" in line:
                errors.append(line)
            elif "warning" in line.lower() and line not in warnings:
                warnings.append(line)

        success = result.returncode == 0

        logger.info(
            f"Compilation {'succeeded' if success else 'failed'} "
            f"in {duration_sec:.2f}s ({len(errors)} errors, {len(warnings)} warnings)"
        )

        return CompilationResult(
            success=success,
            errors=errors,
            warnings=warnings,
            duration_sec=duration_sec,
        )

    except subprocess.TimeoutExpired:
        duration_sec = time.time() - start_time
        logger.error("Compilation timeout after 30s")
        return CompilationResult(
            success=False,
            errors=["Compilation timeout after 30 seconds"],
            warnings=[],
            duration_sec=duration_sec,
        )


def validate_naming(code: str, conventions: dict) -> NamingResult:
    """Validate naming conventions for variables (camelCase).

    Finds all const/let/var declarations and checks that names:
    - Start with a lowercase letter (camelCase)
    - Do not have underscore prefix

    Args:
        code: Raw Vue SFC source code
        conventions: dict from validation_spec.json naming_conventions

    Returns:
        NamingResult with score (0.0 or 1.0) and list of violations
    """
    if not conventions.get("variables"):
        return NamingResult(follows_conventions=True, violations=[], score=1.0)

    violations = []

    var_pattern = r"\b(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)"
    names = re.findall(var_pattern, code)

    if not names:
        return NamingResult(follows_conventions=True, violations=[], score=1.0)

    for name in names:
        # Must start with lowercase letter (not underscore, not uppercase)
        if not name[0].islower():
            violations.append(
                f"Variable '{name}' is not camelCase (must start with lowercase letter)"
            )

    follows_conventions = len(violations) == 0
    score = 1.0 if follows_conventions else 0.0

    logger.info(
        f"Naming validation: {len(names)} variables, "
        f"{len(violations)} violations, score={score}"
    )

    return NamingResult(
        follows_conventions=follows_conventions,
        violations=violations,
        score=score,
    )
