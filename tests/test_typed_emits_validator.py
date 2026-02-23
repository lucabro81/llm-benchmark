"""Tests for typed_emits_composable validator (validate_naming with interface_suffixes)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.refactoring.typed_emits_composable.validator import validate_naming, NamingResult


class TestValidateNamingWithInterfaceSuffixes:
    """validate_naming with interface_suffixes list (typed-emits-composable conventions)."""

    def test_props_and_emits_suffixes_both_valid_scores_one(self):
        """UserProfileProps and UserProfileEmits both satisfy ['Props', 'Emits'] → score 1.0."""
        code = (
            "<script setup lang='ts'>\n"
            "interface UserProfileProps { user: User }\n"
            "interface UserProfileEmits { 'update:user': [user: User] }\n"
            "</script>"
        )
        result = validate_naming(
            code,
            {"interfaces": "PascalCase", "interface_suffixes": ["Props", "Emits"]},
        )
        assert result.score == 1.0
        assert result.follows_conventions is True
        assert len(result.violations) == 0

    def test_emits_suffix_alone_valid_with_interface_suffixes(self):
        """Interface ending with 'Emits' is valid when 'Emits' is in interface_suffixes."""
        code = "<script setup lang='ts'>\ninterface UserProfileEmits { delete: [id: number] }\n</script>"
        result = validate_naming(
            code,
            {"interfaces": "PascalCase", "interface_suffixes": ["Props", "Emits"]},
        )
        assert result.score == 1.0
        assert result.follows_conventions is True

    def test_unknown_suffix_scores_zero(self):
        """Interface with suffix not in interface_suffixes (e.g. 'Config') → score 0.0."""
        code = "<script setup lang='ts'>\ninterface UserProfileConfig { key: string }\n</script>"
        result = validate_naming(
            code,
            {"interfaces": "PascalCase", "interface_suffixes": ["Props", "Emits"]},
        )
        assert result.score == 0.0
        assert result.follows_conventions is False
        assert any("Props" in v or "Emits" in v for v in result.violations)

    def test_pascalcase_still_checked_with_interface_suffixes(self):
        """Lowercase interface name still violates PascalCase even with interface_suffixes."""
        code = "<script setup lang='ts'>\ninterface userProfileProps { name: string }\n</script>"
        result = validate_naming(
            code,
            {"interfaces": "PascalCase", "interface_suffixes": ["Props", "Emits"]},
        )
        assert result.score == 0.0
        assert result.follows_conventions is False
        assert any("PascalCase" in v for v in result.violations)

    def test_one_valid_one_invalid_suffix_scores_zero(self):
        """If one interface has an invalid suffix, whole result is 0.0."""
        code = (
            "<script setup lang='ts'>\n"
            "interface UserProfileProps { user: User }\n"
            "interface UserProfileConfig { key: string }\n"
            "</script>"
        )
        result = validate_naming(
            code,
            {"interfaces": "PascalCase", "interface_suffixes": ["Props", "Emits"]},
        )
        assert result.score == 0.0
        assert result.follows_conventions is False

    def test_legacy_props_suffix_still_works(self):
        """Backward compat: props_interface_suffix (string) still works without interface_suffixes."""
        code = "<script setup lang='ts'>\ninterface HelloWorldProps { title: string }\n</script>"
        result = validate_naming(
            code,
            {"interfaces": "PascalCase", "props_interface_suffix": "Props"},
        )
        assert result.score == 1.0
        assert result.follows_conventions is True

    def test_interface_suffixes_takes_precedence_over_legacy(self):
        """When both interface_suffixes and props_interface_suffix are present, interface_suffixes wins."""
        code = (
            "<script setup lang='ts'>\n"
            "interface UserProfileProps { user: User }\n"
            "interface UserProfileEmits { delete: [id: number] }\n"
            "</script>"
        )
        # interface_suffixes includes both → should pass
        result = validate_naming(
            code,
            {
                "interfaces": "PascalCase",
                "interface_suffixes": ["Props", "Emits"],
                "props_interface_suffix": "Props",  # would fail for Emits if used
            },
        )
        assert result.score == 1.0
        assert result.follows_conventions is True


# ---------------------------------------------------------------------------
# Exception handling in typed_emits_composable test runner
# ---------------------------------------------------------------------------

def _make_typed_emits_fixture(tmp_path):
    """Create a minimal valid fixture directory for typed-emits-composable."""
    fixture_path = tmp_path / "typed-emits-composable"
    fixture_path.mkdir()

    (fixture_path / "prompt.md").write_text("Refactor: {{original_code}}")

    spec = {
        "target_file": "src/components/UserProfile.vue",
        "required_patterns": {"interfaces": ["UserProfileProps", "UserProfileEmits"]},
        "naming_conventions": {"interfaces": "PascalCase", "interface_suffixes": ["Props", "Emits"]},
        "scoring": {"compilation": 0.5, "pattern_match": 0.4, "naming": 0.1},
    }
    (fixture_path / "validation_spec.json").write_text(json.dumps(spec))

    target_project = fixture_path / "target_project"
    components_dir = target_project / "src" / "components"
    components_dir.mkdir(parents=True)
    (components_dir / "UserProfile.vue").write_text(
        "<script setup>\nconst props = defineProps({ user: Object })\n</script>"
    )

    return fixture_path


class TestTypedEmitsRunnerExceptionHandling:
    """Ensure typed_emits_composable test runner handles validation exceptions gracefully."""

    @patch("src.refactoring.typed_emits_composable.test_runner.ollama_client")
    @patch("src.refactoring.typed_emits_composable.test_runner.validator")
    def test_ast_exception_in_typed_emits_runner_handled_gracefully(self, mock_validator, mock_ollama, tmp_path):
        """When validate_ast_structure raises in typed_emits runner, returns degraded BenchmarkResult."""
        from src.refactoring.typed_emits_composable.test_runner import RefactoringTest, BenchmarkResult
        from src.common.ollama_client import ChatResult
        from src.refactoring.typed_emits_composable.validator import CompilationResult, NamingResult

        mock_ollama.chat.return_value = ChatResult(
            response_text="bad code with invalid emits syntax",
            duration_sec=7.5, tokens_generated=40, tokens_per_sec=31.3, success=True,
        )
        mock_validator.validate_compilation.return_value = CompilationResult(
            success=False, errors=["TS2304: error"], warnings=[], duration_sec=1.0
        )
        mock_validator.validate_ast_structure.side_effect = Exception(
            "AST parsing failed: Compile error: [vue/compiler-sfc] Unexpected token (11:3)"
        )
        mock_validator.validate_naming.return_value = NamingResult(
            follows_conventions=False, violations=[], score=0.0
        )

        result = RefactoringTest(model="test-model", fixture_path=_make_typed_emits_fixture(tmp_path)).run(run_number=10)

        # Must not raise — returns a degraded BenchmarkResult
        assert isinstance(result, BenchmarkResult)
        assert result.pattern_score == 0.0
        assert result.run_number == 10
        assert len(result.errors) > 0
        assert any("AST" in e for e in result.errors)
