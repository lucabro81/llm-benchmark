"""AST validation for typed-emits-composable fixture.

Same validation infrastructure as simple_component, with a different
validate_naming() that supports multiple accepted interface suffixes
(e.g. ["Props", "Emits"]) via the interface_suffixes convention key.
"""

import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ASTResult:
    """Result of AST structure validation.

    Attributes:
        has_interfaces: True if TypeScript interface declarations found
        has_type_annotations: True if type annotations found
        has_imports: True if import statements found
        missing: List of missing structure types
        score: Quality score from 0-10 based on structures present
        checks: Per-pattern boolean breakdown (serialized in results JSON)
    """

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
    """Result of TypeScript compilation validation.

    Attributes:
        success: True if TypeScript compilation succeeded
        errors: List of compilation error messages
        warnings: List of compilation warning messages
        duration_sec: Time taken for compilation in seconds
    """

    success: bool
    errors: List[str]
    warnings: List[str]
    duration_sec: float


@dataclass
class NamingResult:
    """Result of naming convention validation.

    Attributes:
        follows_conventions: True if all naming conventions followed
        violations: List of naming convention violations
        score: Quality score from 0.0-1.0 based on convention adherence
    """

    follows_conventions: bool
    violations: List[str]
    score: float


def validate_ast_structure(code: str, expected_structures: dict) -> ASTResult:
    """Validate AST structure of Vue component using Node.js parser.

    Calls a Node.js script that uses @vue/compiler-sfc to parse the
    component and extract AST information about interfaces, type
    annotations, and imports.

    This validates CONFORMANCE to expected patterns, not TypeScript
    compilation correctness (which is the responsibility of the target
    Vue project).

    Args:
        code: Vue component source code
        expected_structures: Dictionary with expected structures
            {
                "interfaces": ["ComponentProps"],
                "type_annotations": ["ComponentProps"],
                "script_lang": ["<script setup lang=\"ts\">"]
            }

    Returns:
        ASTResult with structure analysis and score

    Raises:
        FileNotFoundError: If node or parse script is not available
        Exception: If parsing fails

    Example:
        >>> result = validate_ast_structure(code, expected)
        >>> print(f"Conformance score: {result.score}/10")
    """
    # Create temporary file for parsing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".vue", delete=False) as f:
        f.write(code if code is not None else "")
        temp_file = Path(f.name)

    try:
        # Call Node.js AST parser script
        script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "parse_vue_ast.js"

        result = subprocess.run(
            ["node", str(script_path), str(temp_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            # Check if error is in stderr
            if result.stderr:
                try:
                    error_data = json.loads(result.stderr)
                    raise Exception(f"AST parsing failed: {error_data.get('error', 'Unknown error')}")
                except json.JSONDecodeError:
                    raise Exception(f"AST parsing failed: {result.stderr}")
            raise Exception(f"AST parser returned non-zero exit code: {result.returncode}")

        # Parse JSON output from Node.js script
        try:
            ast_data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse AST output as JSON: {result.stdout}") from e

        # Extract structure information
        has_script_lang_ts = ast_data.get("has_script_lang_ts", False)
        has_interfaces = ast_data.get("has_interfaces", False)
        has_type_annotations = ast_data.get("has_type_annotations", False)
        has_imports = ast_data.get("has_imports", False)

        # Calculate missing structures
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

        # Calculate score (0-10) based on structures present
        # Scoring: interfaces=3.3, type_annotations=3.3, script_lang=3.4
        score = 0.0

        if has_interfaces:
            score += 3.3
        if has_type_annotations:
            score += 3.3
        if has_script_lang_ts:
            score += 3.4

        # Round to 1 decimal place
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
        logger.error("Node.js or parse script not found")
        raise FileNotFoundError("Node.js or parse_vue_ast.js not found") from e

    finally:
        # Cleanup temp file
        if temp_file.exists():
            temp_file.unlink()


def validate_compilation(target_project: Path) -> CompilationResult:
    """Run vue-tsc in target project to validate TypeScript compilation.

    Executes npm run type-check (which runs vue-tsc) in the target project
    directory to verify that the TypeScript code compiles without errors.

    Args:
        target_project: Path to fixture's target_project directory
            (must contain package.json with type-check script)

    Returns:
        CompilationResult with success status, errors, warnings, and duration

    Raises:
        FileNotFoundError: If target_project doesn't exist or lacks package.json

    Example:
        >>> result = validate_compilation(Path("fixtures/refactoring/simple-component/target_project"))
        >>> if result.success:
        ...     print(f"Compilation passed in {result.duration_sec:.2f}s")
        ... else:
        ...     print(f"Errors: {result.errors}")
    """
    import time

    # Validate target_project exists
    if not target_project.exists():
        raise FileNotFoundError(f"Target project not found: {target_project}")

    package_json = target_project / "package.json"
    if not package_json.exists():
        raise FileNotFoundError(f"package.json not found in {target_project}")

    logger.info(f"Running TypeScript compilation in {target_project}")

    # Run npm run type-check
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
    """Validate naming conventions in Vue component code.

    Supports both a list of accepted suffixes (interface_suffixes) and
    the legacy single-suffix key (props_interface_suffix). When both are
    present, interface_suffixes takes precedence.

    Args:
        code: Vue SFC source code
        conventions: Dictionary with naming rules, e.g.:
            {
                "interfaces": "PascalCase",
                "interface_suffixes": ["Props", "Emits"]
            }
            or legacy:
            {
                "interfaces": "PascalCase",
                "props_interface_suffix": "Props"
            }

    Returns:
        NamingResult with violations and score (1.0 = perfect, 0.0 = violations)

    Example:
        >>> code = "interface UserProfileProps { user: User }\\ninterface UserProfileEmits { delete: [id: number] }"
        >>> conventions = {"interfaces": "PascalCase", "interface_suffixes": ["Props", "Emits"]}
        >>> result = validate_naming(code, conventions)
        >>> assert result.score == 1.0
    """
    import re

    violations = []

    # Extract interface names using regex
    interface_pattern = r"interface\s+([a-zA-Z][a-zA-Z0-9]*)"
    interfaces = re.findall(interface_pattern, code)

    # If no interfaces found, consider it valid (nothing to check)
    if not interfaces:
        return NamingResult(
            follows_conventions=True,
            violations=[],
            score=1.0,
        )

    # Resolve which suffix rule to apply
    allowed_suffixes = conventions.get("interface_suffixes")   # list, e.g. ["Props", "Emits"]
    legacy_suffix = conventions.get("props_interface_suffix")  # str, e.g. "Props"

    # Validate each interface
    for interface_name in interfaces:
        # Check PascalCase (first letter uppercase)
        if conventions.get("interfaces") == "PascalCase":
            if not interface_name[0].isupper():
                violations.append(
                    f"Interface '{interface_name}' is not PascalCase (must start with uppercase)"
                )

        # Check suffix: interface_suffixes takes precedence over legacy key
        if allowed_suffixes is not None:
            if not any(interface_name.endswith(s) for s in allowed_suffixes):
                violations.append(
                    f"Interface '{interface_name}' must end with one of: {allowed_suffixes}"
                )
        elif legacy_suffix:
            if not interface_name.endswith(legacy_suffix):
                violations.append(
                    f"Interface '{interface_name}' missing '{legacy_suffix}' suffix"
                )

    # Calculate score
    follows_conventions = len(violations) == 0
    score = 1.0 if follows_conventions else 0.0

    logger.info(
        f"Naming validation: {len(interfaces)} interfaces, "
        f"{len(violations)} violations, score={score}"
    )

    return NamingResult(
        follows_conventions=follows_conventions,
        violations=violations,
        score=score,
    )
