"""Regex-based validation for the nuxt-dt-agent-full fixture.

Full agent test: model uses all tools (read_file, write_file, list_files, run_compilation,
query_rag) to implement OrdersDataTable.vue + columns.ts + optionally types.ts.

Scoring breakdown (validate_ast_structure, 0-10):
  +1  script_lang           <script ... lang="ts"> present
  +1  datatable_component   <DataTable present (with space/newline/>/: lookahead)
  +2  render_function       h( present (word-boundary check)
  +1  currency_formatter    Intl.NumberFormat present
  +1  date_formatter        Intl.DateTimeFormat present
  +1  status_badge          status-related conditional rendering present
  +2  action_handlers       onView (+1) and onCancel (+1) — each checked independently
  +1  column_ids            ≥5 of 6 column ids present: id, customer, status, total, date, actions

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
    """Validate DataTable component patterns using regex on the output source text.

    Args:
        code: Full source of OrdersDataTable.vue (possibly combined with columns.ts).
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

    # --- datatable_component (+1) ---
    if "datatable_component" in expected_patterns:
        found = bool(re.search(r"<DataTable(?=[\s\n>/:{])", code))
        checks["datatable_component"] = found
        if found:
            score += 1.0
        else:
            missing.append("datatable_component")

    # --- render_function (+2) ---
    if "render_function" in expected_patterns:
        found = bool(re.search(r"\bh\(", code))
        checks["render_function"] = found
        if found:
            score += 2.0
        else:
            missing.append("render_function")

    # --- currency_formatter (+1) ---
    if "currency_formatter" in expected_patterns:
        found = bool(re.search(r"Intl\.NumberFormat", code))
        checks["currency_formatter"] = found
        if found:
            score += 1.0
        else:
            missing.append("currency_formatter")

    # --- date_formatter (+1) ---
    if "date_formatter" in expected_patterns:
        found = bool(re.search(r"Intl\.DateTimeFormat", code))
        checks["date_formatter"] = found
        if found:
            score += 1.0
        else:
            missing.append("date_formatter")

    # --- status_badge (+1) ---
    if "status_badge" in expected_patterns:
        found = bool(re.search(
            r"statusClass|statusLabel|statusColor|status\s*===\s*[\"']",
            code
        ))
        checks["status_badge"] = found
        if found:
            score += 1.0
        else:
            missing.append("status_badge")

    # --- action_handlers (+2: +1 for onView, +1 for onCancel) ---
    action_handlers: List[str] = expected_patterns.get("action_handlers", [])
    if action_handlers:
        handler_score = 0.0
        all_found = True
        for handler in action_handlers:
            h_found = bool(re.search(rf"\b{re.escape(handler)}\b", code))
            if h_found:
                handler_score += 1.0
            else:
                all_found = False
                logger.debug(f"action_handler missing: {handler}")
        checks["action_handlers"] = all_found
        if not all_found:
            missing.append("action_handlers")
        score += handler_score

    # --- column_ids (+1 if ≥5 of 6 present) ---
    column_ids: List[str] = expected_patterns.get("column_ids", [])
    if column_ids:
        # Check for id: "X" or id: 'X' patterns for each column id
        present = [
            col_id for col_id in column_ids
            if re.search(rf"""id:\s*[\"']{re.escape(col_id)}[\"']""", code)
        ]
        found = len(present) >= 5
        checks["column_ids"] = found
        if found:
            score += 1.0
        else:
            missing.append("column_ids")
            logger.debug(f"column_ids present: {present}")

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
