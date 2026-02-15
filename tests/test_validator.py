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
    validate_ast_structure,
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
