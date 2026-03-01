"""AST validation for ts-bugfix agent fixture.

Same pipeline as refactoring/simple_component/validator.py:
- validate_compilation: runs vue-tsc via npm run type-check
- validate_ast_structure: calls parse_vue_ast.js (Node.js) for pattern checks
- validate_naming: regex-based interface naming check

Note: script_path calculation uses the same number of .parent calls
(src/agent/ts_bugfix/ = same depth as src/refactoring/simple_component/).
"""

import json
import logging
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class ASTResult:
    """Result of AST structure validation."""

    has_interfaces: bool
    has_type_annotations: bool
    has_imports: bool
    missing: List[str]
    score: float
    checks: dict = None

    def __post_init__(self):
        if self.checks is None:
            self.checks = {
                "has_interfaces": self.has_interfaces,
                "has_type_annotations": self.has_type_annotations,
                "has_imports": self.has_imports,
            }


@dataclass
class CompilationResult:
    """Result of TypeScript compilation validation."""

    success: bool
    errors: List[str]
    warnings: List[str]
    duration_sec: float


@dataclass
class NamingResult:
    """Result of naming convention validation."""

    follows_conventions: bool
    violations: List[str]
    score: float


def validate_ast_structure(code: str, expected_structures: dict) -> ASTResult:
    """Validate AST structure of Vue component using Node.js parser.

    Args:
        code: Vue component source code.
        expected_structures: Dict with expected patterns from validation_spec.json.

    Returns:
        ASTResult with structure analysis and score (0-10).
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".vue", delete=False) as f:
        f.write(code if code is not None else "")
        temp_file = Path(f.name)

    try:
        script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "parse_vue_ast.js"

        result = subprocess.run(
            ["node", str(script_path), str(temp_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            if result.stderr:
                try:
                    error_data = json.loads(result.stderr)
                    raise Exception(f"AST parsing failed: {error_data.get('error', 'Unknown error')}")
                except json.JSONDecodeError:
                    raise Exception(f"AST parsing failed: {result.stderr}")
            raise Exception(f"AST parser returned non-zero exit code: {result.returncode}")

        try:
            ast_data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse AST output as JSON: {result.stdout}") from e

        has_script_lang_ts = ast_data.get("has_script_lang_ts", False)
        has_interfaces = ast_data.get("has_interfaces", False)
        has_type_annotations = ast_data.get("has_type_annotations", False)
        has_imports = ast_data.get("has_imports", False)

        missing = []
        if expected_structures:
            if "interfaces" in expected_structures and not has_interfaces:
                missing.append("interfaces")
            if "type_annotations" in expected_structures and not has_type_annotations:
                missing.append("type_annotations")
            if "script_lang" in expected_structures and not has_script_lang_ts:
                missing.append("script_lang")
            if "imports" in expected_structures and expected_structures["imports"] and not has_imports:
                missing.append("imports")

        score = 0.0
        if has_interfaces:
            score += 3.3
        if has_type_annotations:
            score += 3.3
        if has_script_lang_ts:
            score += 3.4
        score = round(score, 1)

        return ASTResult(
            has_interfaces=has_interfaces,
            has_type_annotations=has_type_annotations,
            has_imports=has_imports,
            missing=missing,
            score=score,
            checks={
                "has_script_lang_ts": has_script_lang_ts,
                "has_interfaces": has_interfaces,
                "has_type_annotations": has_type_annotations,
                "has_imports": has_imports,
            },
        )

    except FileNotFoundError as e:
        raise FileNotFoundError("Node.js or parse_vue_ast.js not found") from e
    finally:
        if temp_file.exists():
            temp_file.unlink()


def validate_compilation(target_project: Path) -> CompilationResult:
    """Run vue-tsc in target project to validate TypeScript compilation.

    Args:
        target_project: Path to fixture's target_project directory.

    Returns:
        CompilationResult with success status, errors, warnings, duration.
    """
    if not target_project.exists():
        raise FileNotFoundError(f"Target project not found: {target_project}")
    if not (target_project / "package.json").exists():
        raise FileNotFoundError(f"package.json not found in {target_project}")

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
            errors=["Compilation timeout after 30 seconds"],
            warnings=[],
            duration_sec=time.time() - start_time,
        )


def validate_naming(code: str, conventions: dict) -> NamingResult:
    """Validate interface naming conventions in Vue component code.

    Args:
        code: Vue SFC source code.
        conventions: Naming rules from validation_spec.json.

    Returns:
        NamingResult with violations and score (1.0 = perfect, 0.0 = violations).
    """
    import re

    violations = []
    interface_pattern = r"interface\s+([a-zA-Z][a-zA-Z0-9]*)"
    interfaces = re.findall(interface_pattern, code)

    if not interfaces:
        return NamingResult(follows_conventions=True, violations=[], score=1.0)

    for interface_name in interfaces:
        if conventions.get("interfaces") == "PascalCase":
            if not interface_name[0].isupper():
                violations.append(
                    f"Interface '{interface_name}' is not PascalCase (must start with uppercase)"
                )
        required_suffix = conventions.get("props_interface_suffix")
        if required_suffix and not interface_name.endswith(required_suffix):
            violations.append(
                f"Interface '{interface_name}' missing '{required_suffix}' suffix"
            )

    follows_conventions = len(violations) == 0
    return NamingResult(
        follows_conventions=follows_conventions,
        violations=violations,
        score=1.0 if follows_conventions else 0.0,
    )
