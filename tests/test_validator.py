"""Tests for validator module."""

import json
from unittest.mock import Mock, patch
from pathlib import Path

import pytest

from src.validator import (
    ASTResult,
    CompilationResult,
    NamingResult,
    validate_ast_structure,
    validate_compilation,
    validate_naming,
)


class TestValidateASTStructure:
    """Test AST scoring logic — all structures present, partial, or missing."""

    @patch("subprocess.run")
    def test_all_structures_present_scores_ten(self, mock_run):
        """Should score 10.0 when interfaces, type_annotations, and lang=ts all present."""
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps({
            "has_script_lang_ts": True,
            "has_interfaces": True,
            "has_type_annotations": True,
            "has_imports": False,
            "interfaces": ["ComponentProps"],
            "type_annotations": ["ComponentProps"],
            "imports": [],
        }), stderr="")

        result = validate_ast_structure(
            "<script setup lang='ts'>...</script>",
            {"interfaces": ["ComponentProps"], "type_annotations": ["defineProps<ComponentProps>"], "script_lang": ["ts"]},
        )

        assert result.score == 10.0
        assert result.has_interfaces is True
        assert result.has_type_annotations is True
        assert len(result.missing) == 0

    @patch("subprocess.run")
    def test_missing_interface_reduces_score(self, mock_run):
        """Should penalise and report missing interface."""
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps({
            "has_script_lang_ts": True,
            "has_interfaces": False,
            "has_type_annotations": True,
            "has_imports": False,
            "interfaces": [],
            "type_annotations": ["string"],
            "imports": [],
        }), stderr="")

        result = validate_ast_structure(
            "<script setup lang='ts'>...</script>",
            {"interfaces": ["SomeInterface"], "type_annotations": ["string"], "script_lang": ["ts"]},
        )

        assert result.has_interfaces is False
        assert result.score < 10.0
        assert "interfaces" in result.missing

    @patch("subprocess.run")
    def test_missing_type_annotation_reduces_score(self, mock_run):
        """Should penalise and report missing type annotation."""
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps({
            "has_script_lang_ts": True,
            "has_interfaces": True,
            "has_type_annotations": False,
            "has_imports": False,
            "interfaces": ["Props"],
            "type_annotations": [],
            "imports": [],
        }), stderr="")

        result = validate_ast_structure(
            "<script setup lang='ts'>...</script>",
            {"interfaces": ["Props"], "type_annotations": ["Props"], "script_lang": ["ts"]},
        )

        assert result.has_type_annotations is False
        assert result.score < 10.0
        assert "type_annotations" in result.missing

    @patch("subprocess.run")
    def test_missing_script_lang_ts_reduces_score(self, mock_run):
        """Should penalise when script tag lacks lang='ts'."""
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps({
            "has_script_lang_ts": False,
            "has_interfaces": True,
            "has_type_annotations": True,
            "has_imports": False,
            "interfaces": ["Props"],
            "type_annotations": ["Props"],
            "imports": [],
        }), stderr="")

        result = validate_ast_structure(
            "<script setup>...</script>",
            {"interfaces": ["Props"], "type_annotations": ["Props"], "script_lang": ["ts"]},
        )

        assert result.score < 10.0
        assert "script_lang" in result.missing

    @patch("subprocess.run")
    def test_partial_structures_score_proportionally(self, mock_run):
        """Should score proportionally: lang=ts (3.4) + type_annotations (3.3) = ~6.7."""
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps({
            "has_script_lang_ts": True,
            "has_interfaces": False,
            "has_type_annotations": True,
            "has_imports": False,
            "interfaces": [],
            "type_annotations": ["string"],
            "imports": [],
        }), stderr="")

        result = validate_ast_structure(
            "<script setup lang='ts'>...</script>",
            {"interfaces": ["Props"], "type_annotations": ["string"], "script_lang": ["ts"]},
        )

        assert 6.0 < result.score < 7.0

    @patch("subprocess.run")
    def test_all_missing_scores_zero(self, mock_run):
        """Should score 0.0 when nothing matches."""
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps({
            "has_script_lang_ts": False,
            "has_interfaces": False,
            "has_type_annotations": False,
            "has_imports": False,
            "interfaces": [],
            "type_annotations": [],
            "imports": [],
        }), stderr="")

        result = validate_ast_structure("", {})

        assert result.score == 0.0

    @patch("subprocess.run")
    def test_commented_code_not_counted(self, mock_run):
        """AST parser should ignore commented-out interfaces."""
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps({
            "has_script_lang_ts": True,
            "has_interfaces": False,  # comment ignored by AST
            "has_type_annotations": False,
            "has_imports": False,
            "interfaces": [],
            "type_annotations": [],
            "imports": [],
        }), stderr="")

        result = validate_ast_structure(
            "<script setup lang='ts'>// interface Props {}</script>",
            {"interfaces": ["Props"], "type_annotations": ["Props"]},
        )

        assert result.has_interfaces is False
        assert result.has_type_annotations is False

    @patch("subprocess.run")
    def test_malformed_vue_raises(self, mock_run):
        """Should raise when Node.js parser returns non-zero exit code."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr='{"error": "parse error"}')

        with pytest.raises(Exception):
            validate_ast_structure("<script setup lang='ts'>interface incomplete", {})

    @patch("subprocess.run")
    def test_node_not_found_raises(self, mock_run):
        """Should propagate FileNotFoundError when Node.js is not installed."""
        mock_run.side_effect = FileNotFoundError("node not found")

        with pytest.raises(FileNotFoundError):
            validate_ast_structure("<script setup lang='ts'></script>", {})

    @patch("subprocess.run")
    def test_invokes_node_parse_script(self, mock_run):
        """Should call the Node.js parse_vue_ast.js helper script."""
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps({
            "has_script_lang_ts": True, "has_interfaces": True,
            "has_type_annotations": True, "has_imports": False,
            "interfaces": ["Props"], "type_annotations": ["Props"], "imports": [],
        }), stderr="")

        validate_ast_structure("<script setup lang='ts'></script>", {})

        call_args = mock_run.call_args[0][0]
        assert "node" in call_args
        assert "parse_vue_ast.js" in " ".join(call_args)


class TestValidateCompilation:
    """Test TypeScript compilation validation via vue-tsc."""

    @patch("subprocess.run")
    def test_clean_compilation_returns_success(self, mock_run):
        """Should return success=True and no errors when vue-tsc exits 0."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = validate_compilation(Path("fixtures/refactoring/simple-component/target_project"))

        assert result.success is True
        assert result.errors == []
        assert result.duration_sec > 0

    @patch("subprocess.run")
    def test_compilation_errors_captured(self, mock_run):
        """Should return success=False and populate errors list on exit code 1."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr=(
            "src/components/HelloWorld.vue:5:7 - error TS2304: Cannot find name 'foo'.\n"
            "src/components/HelloWorld.vue:10:3 - error TS2345: Argument of type 'string' is not assignable.\n"
        ))

        result = validate_compilation(Path("fixtures/refactoring/simple-component/target_project"))

        assert result.success is False
        assert any("TS2304" in e for e in result.errors)
        assert any("TS2345" in e for e in result.errors)

    @patch("subprocess.run")
    def test_warnings_captured_separately(self, mock_run):
        """Should populate warnings list while still reporting success."""
        mock_run.return_value = Mock(returncode=0, stdout=(
            "src/components/HelloWorld.vue:3:7 - warning: Unused variable 'temp'.\n"
        ), stderr="")

        result = validate_compilation(Path("fixtures/refactoring/simple-component/target_project"))

        assert result.success is True
        assert any("Unused variable" in w for w in result.warnings)

    def test_nonexistent_project_raises(self):
        """Should raise FileNotFoundError for a path that does not exist."""
        with pytest.raises(FileNotFoundError):
            validate_compilation(Path("/nonexistent/project"))


class TestValidateNaming:
    """Test naming convention validation (regex-based)."""

    def test_valid_pascalcase_with_props_suffix_scores_one(self):
        """Should score 1.0 for HelloWorldProps (PascalCase + Props suffix)."""
        result = validate_naming(
            "<script setup lang='ts'>\ninterface HelloWorldProps { title: string }\n</script>",
            {"interfaces": "PascalCase", "props_interface_suffix": "Props"},
        )
        assert result.score == 1.0
        assert result.follows_conventions is True
        assert len(result.violations) == 0

    def test_missing_props_suffix_scores_zero(self):
        """Should score 0.0 and report violation when interface lacks 'Props' suffix."""
        result = validate_naming(
            "<script setup lang='ts'>\ninterface HelloWorld { title: string }\n</script>",
            {"interfaces": "PascalCase", "props_interface_suffix": "Props"},
        )
        assert result.score == 0.0
        assert result.follows_conventions is False
        assert any("Props" in v for v in result.violations)

    def test_lowercase_interface_scores_zero(self):
        """Should score 0.0 and report violation for non-PascalCase interface name."""
        result = validate_naming(
            "<script setup lang='ts'>\ninterface helloWorldProps { title: string }\n</script>",
            {"interfaces": "PascalCase", "props_interface_suffix": "Props"},
        )
        assert result.score == 0.0
        assert result.follows_conventions is False
        assert any("PascalCase" in v for v in result.violations)

    def test_no_interface_passes_with_full_score(self):
        """Should score 1.0 when no interfaces present (nothing to violate)."""
        result = validate_naming(
            "<script setup>\nconst props = defineProps({ title: String })\n</script>",
            {"interfaces": "PascalCase", "props_interface_suffix": "Props"},
        )
        assert result.score == 1.0
        assert result.follows_conventions is True

    def test_any_interface_without_props_suffix_fails(self):
        """Should fail if any interface in the file lacks the Props suffix."""
        result = validate_naming(
            "<script setup lang='ts'>\ninterface UserProfile { name: string }\ninterface HelloWorldProps { user: UserProfile }\n</script>",
            {"interfaces": "PascalCase", "props_interface_suffix": "Props"},
        )
        assert result.score == 0.0
        assert result.follows_conventions is False


class TestValidatorIntegration:
    """Integration tests (require node installed)."""

    @pytest.mark.integration
    def test_real_ast_parsing(self):
        """Integration test with real Node.js AST parser.
        Requires: node installed + npm install in fixture target_project
        (needs @vue/compiler-sfc in node_modules).
        """
        import subprocess
        # Fail fast with a clear message if @vue/compiler-sfc is not installed
        check = subprocess.run(
            ["node", "-e", "require('@vue/compiler-sfc')"],
            capture_output=True, text=True
        )
        if check.returncode != 0:
            pytest.fail(
                "@vue/compiler-sfc not found. Run: npm install (in project root)"
            )

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
        result = validate_ast_structure(
            code,
            {
                "interfaces": ["ComponentProps"],
                "type_annotations": ["ComponentProps"],
                "script_lang": ["ts"],
            },
        )

        assert result.score == 10.0
        assert result.has_interfaces is True
        assert result.has_type_annotations is True
        assert len(result.missing) == 0
