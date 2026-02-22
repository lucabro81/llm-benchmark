"""Tests for typed_emits_composable validator (validate_naming with interface_suffixes)."""

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
