"""Tests for validator module following TDD approach.

This test suite validates AST structure checking for Vue components.
Note: TypeScript compilation testing has been removed as that is the
responsibility of the target Vue project, not this benchmarking tool.
"""

import json
from dataclasses import is_dataclass
from unittest.mock import Mock, patch

import pytest

from src.validator import (
    ASTResult,
    CompilationResult,
    NamingResult,
    validate_ast_structure,
    validate_compilation,
    validate_naming,
)


class TestASTResultDataclass:
    """Test ASTResult dataclass structure and properties."""

    def test_ast_result_is_dataclass(self):
        """ASTResult should be a dataclass."""
        assert is_dataclass(ASTResult)

    def test_ast_result_complete_data(self):
        """ASTResult should store all AST analysis data."""
        result = ASTResult(
            has_interfaces=True,
            has_type_annotations=True,
            has_imports=False,
            missing=[],
            score=10.0,
        )

        assert result.has_interfaces is True
        assert result.has_type_annotations is True
        assert result.has_imports is False
        assert result.missing == []
        assert result.score == 10.0

    def test_ast_result_with_missing_structures(self):
        """ASTResult should track missing structures."""
        result = ASTResult(
            has_interfaces=False,
            has_type_annotations=True,
            has_imports=False,
            missing=["interfaces", "imports"],
            score=3.3,
        )

        assert result.has_interfaces is False
        assert "interfaces" in result.missing
        assert "imports" in result.missing
        assert result.score == 3.3


class TestValidateASTStructure:
    """Test AST structure validation using Node.js parser."""

    @patch("subprocess.run")
    def test_full_typescript_component_scores_ten(self, mock_run):
        """Should return score=10.0 for component with all structures."""
        ast_output = {
            "has_script_lang_ts": True,
            "has_interfaces": True,
            "has_type_annotations": True,
            "has_imports": False,
            "interfaces": ["ComponentProps"],
            "type_annotations": ["ComponentProps"],
            "imports": [],
        }
        mock_run.return_value = Mock(
            returncode=0, stdout=json.dumps(ast_output), stderr=""
        )

        code = """
<script setup lang="ts">
interface ComponentProps {
  title: string
}
const props = defineProps<ComponentProps>()
</script>
"""
        expected_structures = {
            "interfaces": ["ComponentProps"],
            "type_annotations": ["defineProps<ComponentProps>"],
            "script_lang": ["<script setup lang=\"ts\">"],
        }

        result = validate_ast_structure(code, expected_structures)

        assert result.score == 10.0
        assert result.has_interfaces is True
        assert result.has_type_annotations is True
        assert len(result.missing) == 0

    @patch("subprocess.run")
    def test_missing_interfaces_reduces_score(self, mock_run):
        """Should reduce score when interfaces are missing."""
        ast_output = {
            "has_script_lang_ts": True,
            "has_interfaces": False,  # Missing!
            "has_type_annotations": True,
            "has_imports": False,
            "interfaces": [],
            "type_annotations": ["string"],
            "imports": [],
        }
        mock_run.return_value = Mock(
            returncode=0, stdout=json.dumps(ast_output), stderr=""
        )

        code = "<script setup lang='ts'>const x: string = 'foo'</script>"
        expected_structures = {
            "interfaces": ["SomeInterface"],
            "type_annotations": ["string"],
            "script_lang": ["<script setup lang=\"ts\">"],
        }

        result = validate_ast_structure(code, expected_structures)

        assert result.has_interfaces is False
        assert result.score < 10.0
        assert "interfaces" in result.missing

    @patch("subprocess.run")
    def test_missing_type_annotations_reduces_score(self, mock_run):
        """Should reduce score when type annotations are missing."""
        ast_output = {
            "has_script_lang_ts": True,
            "has_interfaces": True,
            "has_type_annotations": False,  # Missing!
            "has_imports": False,
            "interfaces": ["Props"],
            "type_annotations": [],
            "imports": [],
        }
        mock_run.return_value = Mock(
            returncode=0, stdout=json.dumps(ast_output), stderr=""
        )

        code = """
<script setup lang="ts">
interface Props {
  title: string
}
</script>
"""
        expected_structures = {
            "interfaces": ["Props"],
            "type_annotations": ["Props"],
            "script_lang": ["<script setup lang=\"ts\">"],
        }

        result = validate_ast_structure(code, expected_structures)

        assert result.has_type_annotations is False
        assert result.score < 10.0
        assert "type_annotations" in result.missing

    @patch("subprocess.run")
    def test_missing_script_lang_ts_reduces_score(self, mock_run):
        """Should reduce score when lang='ts' is missing."""
        ast_output = {
            "has_script_lang_ts": False,  # Missing!
            "has_interfaces": True,
            "has_type_annotations": True,
            "has_imports": False,
            "interfaces": ["Props"],
            "type_annotations": ["Props"],
            "imports": [],
        }
        mock_run.return_value = Mock(
            returncode=0, stdout=json.dumps(ast_output), stderr=""
        )

        code = """
<script setup>
interface Props {
  title: string
}
</script>
"""
        expected_structures = {
            "interfaces": ["Props"],
            "type_annotations": ["Props"],
            "script_lang": ["<script setup lang=\"ts\">"],
        }

        result = validate_ast_structure(code, expected_structures)

        assert result.score < 10.0

    @patch("subprocess.run")
    def test_empty_code_returns_zero_score(self, mock_run):
        """Should return score=0.0 for empty code."""
        ast_output = {
            "has_script_lang_ts": False,
            "has_interfaces": False,
            "has_type_annotations": False,
            "has_imports": False,
            "interfaces": [],
            "type_annotations": [],
            "imports": [],
        }
        mock_run.return_value = Mock(
            returncode=0, stdout=json.dumps(ast_output), stderr=""
        )

        code = ""
        expected_structures = {}

        result = validate_ast_structure(code, expected_structures)

        assert result.score == 0.0

    @patch("subprocess.run")
    def test_tracks_missing_structures_in_list(self, mock_run):
        """Should list all missing structures in missing field."""
        ast_output = {
            "has_script_lang_ts": False,
            "has_interfaces": False,
            "has_type_annotations": False,
            "has_imports": False,
            "interfaces": [],
            "type_annotations": [],
            "imports": [],
        }
        mock_run.return_value = Mock(
            returncode=0, stdout=json.dumps(ast_output), stderr=""
        )

        code = "<script setup>const x = 1</script>"
        expected_structures = {
            "interfaces": ["Props"],
            "type_annotations": ["Props"],
            "script_lang": ["<script setup lang=\"ts\">"],
        }

        result = validate_ast_structure(code, expected_structures)

        assert "interfaces" in result.missing
        assert "type_annotations" in result.missing
        assert "script_lang" in result.missing

    @patch("subprocess.run")
    def test_partial_structures_get_proportional_score(self, mock_run):
        """Should score proportionally when some structures present."""
        ast_output = {
            "has_script_lang_ts": True,  # Present (3.4 points)
            "has_interfaces": False,  # Missing (0 points)
            "has_type_annotations": True,  # Present (3.3 points)
            "has_imports": False,
            "interfaces": [],
            "type_annotations": ["string"],
            "imports": [],
        }
        mock_run.return_value = Mock(
            returncode=0, stdout=json.dumps(ast_output), stderr=""
        )

        code = "<script setup lang='ts'>const x: string = 'foo'</script>"
        expected_structures = {
            "interfaces": ["Props"],
            "type_annotations": ["string"],
            "script_lang": ["<script setup lang=\"ts\">"],
        }

        result = validate_ast_structure(code, expected_structures)

        # Score should be 3.4 + 3.3 = 6.7
        assert 6.0 < result.score < 7.0

    @patch("subprocess.run")
    def test_ignores_commented_code(self, mock_run):
        """Should ignore commented code (no false positives)."""
        # The Node.js AST parser inherently ignores comments
        # because it parses actual AST nodes, not text
        ast_output = {
            "has_script_lang_ts": True,
            "has_interfaces": False,  # Comment doesn't count
            "has_type_annotations": False,
            "has_imports": False,
            "interfaces": [],
            "type_annotations": [],
            "imports": [],
        }
        mock_run.return_value = Mock(
            returncode=0, stdout=json.dumps(ast_output), stderr=""
        )

        code = """
<script setup lang="ts">
// interface Props { title: string }
// const props = defineProps<Props>()
</script>
"""
        expected_structures = {
            "interfaces": ["Props"],
            "type_annotations": ["Props"],
        }

        result = validate_ast_structure(code, expected_structures)

        assert result.has_interfaces is False
        assert result.has_type_annotations is False

    @patch("subprocess.run")
    def test_handles_malformed_vue_file(self, mock_run):
        """Should handle parsing errors from malformed Vue files."""
        error_output = {"error": "Parse error: Unexpected token"}
        mock_run.return_value = Mock(
            returncode=1, stdout="", stderr=json.dumps(error_output)
        )

        code = "<script setup lang='ts'>interface incomplete"
        expected_structures = {}

        with pytest.raises(Exception):
            validate_ast_structure(code, expected_structures)

    @patch("subprocess.run")
    def test_calls_node_script_correctly(self, mock_run):
        """Should call Node.js parse script with correct arguments."""
        ast_output = {
            "has_script_lang_ts": True,
            "has_interfaces": True,
            "has_type_annotations": True,
            "has_imports": False,
            "interfaces": ["Props"],
            "type_annotations": ["Props"],
            "imports": [],
        }
        mock_run.return_value = Mock(
            returncode=0, stdout=json.dumps(ast_output), stderr=""
        )

        code = "<script setup lang='ts'></script>"
        expected_structures = {}

        validate_ast_structure(code, expected_structures)

        # Verify node script was called
        call_args = mock_run.call_args[0][0]
        assert "node" in call_args
        assert "parse_vue_ast.js" in " ".join(call_args)

    @patch("subprocess.run")
    def test_parses_json_response_from_script(self, mock_run):
        """Should correctly parse JSON response from Node.js script."""
        ast_output = {
            "has_script_lang_ts": True,
            "has_interfaces": True,
            "has_type_annotations": True,
            "has_imports": True,
            "interfaces": ["Props", "State"],
            "type_annotations": ["Props", "State", "string"],
            "imports": [{"source": "vue", "isTypeOnly": False}],
        }
        mock_run.return_value = Mock(
            returncode=0, stdout=json.dumps(ast_output), stderr=""
        )

        code = "<script setup lang='ts'></script>"
        expected_structures = {}

        result = validate_ast_structure(code, expected_structures)

        assert result.has_interfaces is True
        assert result.has_type_annotations is True
        assert result.has_imports is True

    @patch("subprocess.run")
    def test_handles_node_script_unavailable(self, mock_run):
        """Should raise error when Node.js script is not available."""
        mock_run.side_effect = FileNotFoundError("node not found")

        code = "<script setup lang='ts'></script>"
        expected_structures = {}

        with pytest.raises(FileNotFoundError):
            validate_ast_structure(code, expected_structures)


class TestValidatorEdgeCases:
    """Test edge cases and error scenarios."""

    @patch("subprocess.run")
    def test_handles_unicode_in_code(self, mock_run):
        """Should handle Unicode characters in Vue code."""
        ast_output = {
            "has_script_lang_ts": True,
            "has_interfaces": True,
            "has_type_annotations": True,
            "has_imports": False,
            "interfaces": ["Props"],
            "type_annotations": ["Props"],
            "imports": [],
        }
        mock_run.return_value = Mock(
            returncode=0, stdout=json.dumps(ast_output), stderr=""
        )

        code = """
<script setup lang="ts">
interface Props {
  title: string  // Título en español 🇪🇸
}
const props = defineProps<Props>()
</script>
"""
        expected_structures = {}

        result = validate_ast_structure(code, expected_structures)

        assert isinstance(result, ASTResult)


class TestValidatorIntegration:
    """Integration tests (require node installed)."""

    @pytest.mark.integration
    def test_real_ast_parsing(self):
        """Integration test with real Node.js AST parser."""
        code = """
<script setup lang="ts">
interface ComponentProps {
  title: string
  items: string[]
}

const props = defineProps<ComponentProps>()
</script>

<template>
  <div>{{ title }}</div>
</template>
"""

        expected_structures = {
            "interfaces": ["ComponentProps"],
            "type_annotations": ["ComponentProps"],
            "script_lang": ["<script setup lang=\"ts\">"],
        }

        result = validate_ast_structure(code, expected_structures)

        assert result.score == 10.0
        assert result.has_interfaces is True
        assert result.has_type_annotations is True
        assert len(result.missing) == 0


class TestCompilationResultDataclass:
    """Test CompilationResult dataclass structure and properties."""

    def test_compilation_result_is_dataclass(self):
        """CompilationResult should be a dataclass."""
        assert is_dataclass(CompilationResult)

    def test_compilation_result_success(self):
        """CompilationResult should store success state."""
        result = CompilationResult(
            success=True,
            errors=[],
            warnings=[],
            duration_sec=2.5,
        )

        assert result.success is True
        assert result.errors == []
        assert result.warnings == []
        assert result.duration_sec == 2.5

    def test_compilation_result_with_errors(self):
        """CompilationResult should store compilation errors."""
        result = CompilationResult(
            success=False,
            errors=["TS2304: Cannot find name 'foo'.", "TS2345: Type error"],
            warnings=["Warning: unused variable"],
            duration_sec=1.2,
        )

        assert result.success is False
        assert len(result.errors) == 2
        assert "TS2304" in result.errors[0]
        assert len(result.warnings) == 1


class TestCompilationValidation:
    """Test TypeScript compilation validation via vue-tsc."""

    @patch("subprocess.run")
    def test_successful_compilation(self, mock_run):
        """Should return success=True when vue-tsc passes."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )

        from pathlib import Path
        result = validate_compilation(Path("fixtures/refactoring/simple-component/target_project"))

        assert result.success is True
        assert result.errors == []
        assert result.duration_sec > 0

        # Verify subprocess call
        call_args = mock_run.call_args[0][0]
        assert "npm" in call_args
        assert "type-check" in call_args

    @patch("subprocess.run")
    def test_compilation_with_errors(self, mock_run):
        """Should return success=False and capture TypeScript errors."""
        error_output = """
src/components/HelloWorld.vue:5:7 - error TS2304: Cannot find name 'foo'.

5   const foo = bar;
          ~~~

src/components/HelloWorld.vue:10:3 - error TS2345: Argument of type 'string' is not assignable.

10   props.count = "invalid";
     ~~~~~~~~~~~
"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr=error_output,
        )

        from pathlib import Path
        result = validate_compilation(Path("fixtures/refactoring/simple-component/target_project"))

        assert result.success is False
        assert len(result.errors) > 0
        assert any("TS2304" in err for err in result.errors)
        assert any("TS2345" in err for err in result.errors)

    @patch("subprocess.run")
    def test_compilation_with_warnings(self, mock_run):
        """Should capture warnings separately from errors."""
        warning_output = """
src/components/HelloWorld.vue:3:7 - warning: Unused variable 'temp'.

3   const temp = 123;
          ~~~~
"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=warning_output,
            stderr="",
        )

        from pathlib import Path
        result = validate_compilation(Path("fixtures/refactoring/simple-component/target_project"))

        assert result.success is True
        assert len(result.warnings) > 0
        assert any("Unused variable" in warn for warn in result.warnings)

    def test_compilation_nonexistent_project(self):
        """Should raise FileNotFoundError for nonexistent project."""
        from pathlib import Path
        with pytest.raises(FileNotFoundError):
            validate_compilation(Path("/nonexistent/project"))


class TestNamingResultDataclass:
    """Test NamingResult dataclass structure and properties."""

    def test_naming_result_is_dataclass(self):
        """NamingResult should be a dataclass."""
        assert is_dataclass(NamingResult)

    def test_naming_result_valid(self):
        """NamingResult should store validation state."""
        result = NamingResult(
            follows_conventions=True,
            violations=[],
            score=1.0,
        )

        assert result.follows_conventions is True
        assert result.violations == []
        assert result.score == 1.0

    def test_naming_result_with_violations(self):
        """NamingResult should track naming violations."""
        result = NamingResult(
            follows_conventions=False,
            violations=["Interface not PascalCase", "Missing 'Props' suffix"],
            score=0.0,
        )

        assert result.follows_conventions is False
        assert len(result.violations) == 2
        assert result.score == 0.0


class TestNamingValidation:
    """Test naming convention validation."""

    def test_valid_interface_naming(self):
        """Should return score=1.0 for HelloWorldProps."""
        code = """
<script setup lang="ts">
interface HelloWorldProps {
  title: string
  count: number
}
</script>
"""
        conventions = {
            "interfaces": "PascalCase",
            "props_interface_suffix": "Props"
        }

        result = validate_naming(code, conventions)

        assert result.score == 1.0
        assert result.follows_conventions is True
        assert len(result.violations) == 0

    def test_invalid_interface_no_suffix(self):
        """Should return score=0.0 for interface without 'Props' suffix."""
        code = """
<script setup lang="ts">
interface HelloWorld {
  title: string
}
</script>
"""
        conventions = {
            "interfaces": "PascalCase",
            "props_interface_suffix": "Props"
        }

        result = validate_naming(code, conventions)

        assert result.score == 0.0
        assert result.follows_conventions is False
        assert any("Props" in v for v in result.violations)

    def test_invalid_interface_not_pascalcase(self):
        """Should return score=0.0 for lowercase interface name."""
        code = """
<script setup lang="ts">
interface helloWorldProps {
  title: string
}
</script>
"""
        conventions = {
            "interfaces": "PascalCase",
            "props_interface_suffix": "Props"
        }

        result = validate_naming(code, conventions)

        assert result.score == 0.0
        assert result.follows_conventions is False
        assert any("PascalCase" in v for v in result.violations)

    def test_no_interface_found(self):
        """Should handle code without interfaces gracefully."""
        code = """
<script setup>
const props = defineProps({
  title: String
})
</script>
"""
        conventions = {
            "interfaces": "PascalCase",
            "props_interface_suffix": "Props"
        }

        result = validate_naming(code, conventions)

        # No interface = pass (nothing to validate)
        assert result.score == 1.0
        assert result.follows_conventions is True

    def test_multiple_interfaces(self):
        """Should validate all interfaces in code."""
        code = """
<script setup lang="ts">
interface UserProfile {
  name: string
}

interface HelloWorldProps {
  user: UserProfile
}
</script>
"""
        conventions = {
            "interfaces": "PascalCase",
            "props_interface_suffix": "Props"
        }

        result = validate_naming(code, conventions)

        # UserProfile doesn't have "Props" suffix → violation
        assert result.score == 0.0
        assert result.follows_conventions is False
