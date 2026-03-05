"""Regex-based validation for the nuxt-form-agent-rag fixture.

Single-shot creation test: model receives full component API docs inline in the prompt
and outputs a single RegistrationForm.vue with types defined inline.

Scoring breakdown (validate_ast_structure, 0-10):
  +1  script_lang           <script ... lang="ts"> present
  +1  form_component        <Form present
  +2  controlled_components ≥3 of 4 types present (Input, RadioGroup, Checkbox, Textarea)
  +1  conditional_rendering v-if present
  +2  zod_schema            z.object( present
  +2  required_fields       all 4 required field names present (username, email, role, bio)
  +1  conditional_fields    ≥2 of 3 conditional field names present (newsletter, frequency, otherInfo)

validate_compilation runs `npm run <compilation_command>` from `compilation_cwd`.
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
    """Validate component patterns using regex on the output source text.

    Args:
        code: Full source of RegistrationForm.vue (with inline types).
        expected_patterns: dict from validation_spec.json required_patterns.

    Returns:
        ASTResult with score (0-10) and list of missing pattern keys.
    """
    if not code or not expected_patterns:
        return ASTResult(score=0.0, missing=list(expected_patterns.keys()) if expected_patterns else [])

    missing = []
    score = 0.0
    checks = {}

    # --- script_lang (+1) ---
    if expected_patterns.get("script_lang") == "ts":
        found = bool(re.search(r"<script[^>]+lang=[\"']ts[\"']", code))
        checks["script_lang"] = found
        if found:
            score += 1.0
        else:
            missing.append("script_lang")

    # --- form_component (+1) ---
    if "form_component" in expected_patterns:
        pattern = re.escape(expected_patterns["form_component"]) + r"(?=[\s\n>])"
        found = bool(re.search(pattern, code))
        checks["form_component"] = found
        if found:
            score += 1.0
        else:
            missing.append("form_component")

    # --- controlled_components (+2 if ≥3 of 4 present) ---
    component_list: List[str] = expected_patterns.get("controlled_components", [])
    if component_list:
        present = [c for c in component_list if re.search(re.escape(c), code)]
        found = len(present) >= 3
        checks["controlled_components"] = found
        if found:
            score += 2.0
        else:
            missing.append("controlled_components")
            logger.debug(f"controlled_components present: {present}")

    # --- conditional_rendering (+1) ---
    if "conditional_rendering" in expected_patterns:
        found = bool(re.search(r"\bv-if\b", code))
        checks["conditional_rendering"] = found
        if found:
            score += 1.0
        else:
            missing.append("conditional_rendering")

    # --- zod_schema (+2) ---
    if "zod_schema" in expected_patterns:
        found = bool(re.search(r"\bz\.object\s*\(", code))
        checks["zod_schema"] = found
        if found:
            score += 2.0
        else:
            missing.append("zod_schema")

    # --- required_fields (+2 if all present) ---
    required_fields: List[str] = expected_patterns.get("required_fields", [])
    if required_fields:
        missing_fields = [f for f in required_fields if not re.search(rf"\b{re.escape(f)}\b", code)]
        found = len(missing_fields) == 0
        checks["required_fields"] = found
        if found:
            score += 2.0
        else:
            missing.append("required_fields")
            logger.debug(f"Missing required fields: {missing_fields}")

    # --- conditional_fields (+1 if ≥2 of N present) ---
    conditional_fields: List[str] = expected_patterns.get("conditional_fields", [])
    if conditional_fields:
        present_cond = [f for f in conditional_fields if re.search(rf"\b{re.escape(f)}\b", code)]
        found = len(present_cond) >= 2
        checks["conditional_fields"] = found
        if found:
            score += 1.0
        else:
            missing.append("conditional_fields")
            logger.debug(f"conditional_fields present: {present_cond}")

    logger.info(f"Pattern score: {score}/10, missing: {missing}")
    return ASTResult(score=round(score, 1), missing=missing, checks=checks)


def validate_compilation(
    target_project: Path,
    compilation_command: str,
    compilation_cwd: Path,
) -> CompilationResult:
    """Run `npm run <compilation_command>` from `compilation_cwd`.

    Args:
        target_project: Root of the fixture's target_project (for existence check).
        compilation_command: npm script name (e.g. 'check-types').
        compilation_cwd: Directory from which to run npm (e.g. target_project/apps/web).

    Returns:
        CompilationResult with success flag, errors, warnings, duration.
    """
    if not target_project.exists():
        raise FileNotFoundError(f"Target project not found: {target_project}")
    if not compilation_cwd.exists():
        raise FileNotFoundError(f"Compilation cwd not found: {compilation_cwd}")

    start_time = time.time()
    try:
        result = subprocess.run(
            ["npm", "run", compilation_command],
            cwd=compilation_cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        duration_sec = time.time() - start_time

        errors = []
        warnings = []
        for line in (result.stdout + "\n" + result.stderr).split("\n"):
            line = line.strip()
            if "error TS" in line or " - error" in line:
                errors.append(line)
            elif "warning" in line.lower() and line not in warnings:
                warnings.append(line)

        return CompilationResult(
            success=result.returncode == 0,
            errors=errors,
            warnings=warnings,
            duration_sec=duration_sec,
        )

    except subprocess.TimeoutExpired:
        return CompilationResult(
            success=False,
            errors=["Compilation timeout after 60 seconds"],
            warnings=[],
            duration_sec=time.time() - start_time,
        )


def validate_naming(code: str, conventions: dict) -> NamingResult:
    """Validate camelCase naming convention for variable declarations.

    Args:
        code: Source code of the component.
        conventions: dict from validation_spec.json naming_conventions.

    Returns:
        NamingResult with score (0.0 or 1.0) and violation list.
    """
    if not conventions.get("variables"):
        return NamingResult(follows_conventions=True, violations=[], score=1.0)

    var_pattern = r"\b(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)"
    names = re.findall(var_pattern, code)

    if not names:
        return NamingResult(follows_conventions=True, violations=[], score=1.0)

    violations = [
        f"Variable '{name}' is not camelCase (must start with lowercase letter)"
        for name in names
        if not name[0].islower()
    ]

    follows = len(violations) == 0
    return NamingResult(
        follows_conventions=follows,
        violations=violations,
        score=1.0 if follows else 0.0,
    )
