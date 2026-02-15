"""AST validation for Vue components.

This module provides AST structure validation for Vue components generated
by LLMs, checking conformance to expected patterns and coding standards.

Note: TypeScript compilation is NOT performed by this tool.
      That is the responsibility of the target Vue project's vue-tsc setup.
      This tool only validates that the generated code follows expected
      structural patterns (interfaces, type annotations, etc.).
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
    """

    has_interfaces: bool
    has_type_annotations: bool
    has_imports: bool
    missing: List[str]
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
        script_path = Path(__file__).parent.parent / "scripts" / "parse_vue_ast.js"

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
        )

    except FileNotFoundError as e:
        logger.error("Node.js or parse script not found")
        raise FileNotFoundError("Node.js or parse_vue_ast.js not found") from e

    finally:
        # Cleanup temp file
        if temp_file.exists():
            temp_file.unlink()
