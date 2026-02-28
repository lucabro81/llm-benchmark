"""Tests for veevalidate_zod_form validator (regex-based pattern checks)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.creation.veevalidate_zod_form.validator import (
    validate_ast_structure,
    validate_naming,
    ASTResult,
    NamingResult,
)


# ---------------------------------------------------------------------------
# Fixture: complete valid component
# ---------------------------------------------------------------------------

COMPLETE_COMPONENT = """
<script setup lang="ts">
import { z } from 'zod'
import { useForm } from 'vee-validate'
import { toTypedSchema } from '@vee-validate/zod'

const registrationSchema = z.object({
  username: z.string().min(3),
  email: z.string().email(),
  password: z.string().min(8),
  role: z.enum(['user', 'admin']),
  terms: z.literal(true),
  bio: z.string().optional(),
})

const { errors, handleSubmit } = useForm({
  validationSchema: toTypedSchema(registrationSchema),
})

const { value: username } = useField('username')
const { value: email } = useField('email')
const { value: password } = useField('password')
const { value: role } = useField('role')
const { value: terms } = useField('terms')
const { value: bio } = useField('bio')

const onSubmit = handleSubmit((values) => {
  console.log(values)
})
</script>

<template>
  <form @submit="onSubmit">
    <div>
      <label>Username</label>
      <input v-model="username" type="text" />
      <span>{{ errors.username }}</span>
    </div>
    <div>
      <label>Email</label>
      <input v-model="email" type="email" />
      <span>{{ errors.email }}</span>
    </div>
    <div>
      <label>Password</label>
      <input v-model="password" type="password" />
      <span>{{ errors.password }}</span>
    </div>
    <div>
      <label>Role</label>
      <input v-model="role" type="radio" value="user" />
      <input v-model="role" type="radio" value="admin" />
      <span>{{ errors.role }}</span>
    </div>
    <div>
      <input v-model="terms" type="checkbox" />
      <span>{{ errors.terms }}</span>
    </div>
    <div>
      <textarea v-model="bio"></textarea>
      <span>{{ errors.bio }}</span>
    </div>
    <button type="submit">Register</button>
  </form>
</template>
"""


class TestValidateAstStructure:
    """validate_ast_structure: regex-based pattern checks."""

    def test_complete_component_scores_ten(self):
        """All patterns present → score=10.0, no missing."""
        spec = {
            "script_lang": "ts",
            "use_form": "useForm",
            "zod_schema": "z.object",
            "typed_schema": "toTypedSchema",
            "fields": ["username", "email", "password", "role", "terms", "bio"],
            "error_display": "errors",
        }
        result = validate_ast_structure(COMPLETE_COMPONENT, spec)
        assert result.score == 10.0
        assert result.missing == []

    def test_missing_useform_reduces_score(self):
        """Component without useForm() → score reduced by 2."""
        code = COMPLETE_COMPONENT.replace("useForm", "useFORM_REMOVED")
        spec = {
            "script_lang": "ts",
            "use_form": "useForm",
            "zod_schema": "z.object",
            "typed_schema": "toTypedSchema",
            "fields": ["username", "email", "password", "role", "terms", "bio"],
            "error_display": "errors",
        }
        result = validate_ast_structure(code, spec)
        assert result.score == 8.0
        assert "use_form" in result.missing

    def test_missing_zod_schema_reduces_score(self):
        """Component without z.object() → score reduced by 2."""
        code = COMPLETE_COMPONENT.replace("z.object", "z_REMOVED.object")
        spec = {
            "script_lang": "ts",
            "use_form": "useForm",
            "zod_schema": "z.object",
            "typed_schema": "toTypedSchema",
            "fields": ["username", "email", "password", "role", "terms", "bio"],
            "error_display": "errors",
        }
        result = validate_ast_structure(code, spec)
        assert result.score == 8.0
        assert "zod_schema" in result.missing

    def test_missing_typed_schema_reduces_score(self):
        """Component without toTypedSchema() → score reduced by 2."""
        code = COMPLETE_COMPONENT.replace("toTypedSchema", "REMOVED")
        spec = {
            "script_lang": "ts",
            "use_form": "useForm",
            "zod_schema": "z.object",
            "typed_schema": "toTypedSchema",
            "fields": ["username", "email", "password", "role", "terms", "bio"],
            "error_display": "errors",
        }
        result = validate_ast_structure(code, spec)
        assert result.score == 8.0
        assert "typed_schema" in result.missing

    def test_missing_some_fields_reduces_score(self):
        """Component missing 'bio' and 'terms' fields → score reduced by 2."""
        code = COMPLETE_COMPONENT.replace("bio", "BIO_REMOVED").replace("terms", "TERMS_REMOVED")
        spec = {
            "script_lang": "ts",
            "use_form": "useForm",
            "zod_schema": "z.object",
            "typed_schema": "toTypedSchema",
            "fields": ["username", "email", "password", "role", "terms", "bio"],
            "error_display": "errors",
        }
        result = validate_ast_structure(code, spec)
        assert result.score == 8.0
        assert "fields" in result.missing

    def test_missing_error_display_reduces_score(self):
        """Component without errors.* in template → score reduced by 2."""
        code = COMPLETE_COMPONENT.replace("errors.", "ERR_REMOVED.")
        spec = {
            "script_lang": "ts",
            "use_form": "useForm",
            "zod_schema": "z.object",
            "typed_schema": "toTypedSchema",
            "fields": ["username", "email", "password", "role", "terms", "bio"],
            "error_display": "errors",
        }
        result = validate_ast_structure(code, spec)
        assert result.score == 8.0
        assert "error_display" in result.missing

    def test_empty_component_scores_zero(self):
        """Empty component → score=0.0, all patterns missing."""
        code = "<script setup lang='ts'>\n</script>\n<template>\n</template>"
        spec = {
            "script_lang": "ts",
            "use_form": "useForm",
            "zod_schema": "z.object",
            "typed_schema": "toTypedSchema",
            "fields": ["username", "email", "password", "role", "terms", "bio"],
            "error_display": "errors",
        }
        result = validate_ast_structure(code, spec)
        # script_lang is present → +2, rest missing → 2/10
        assert result.score == 2.0
        assert "use_form" in result.missing
        assert "zod_schema" in result.missing
        assert "fields" in result.missing
        assert "error_display" in result.missing

    def test_completely_empty_string_scores_zero(self):
        """Completely empty string → score=0.0."""
        result = validate_ast_structure("", {})
        assert result.score == 0.0

    def test_no_script_lang_ts_reduces_score(self):
        """Component without lang='ts' on script tag → score reduced by 2."""
        code = COMPLETE_COMPONENT.replace('lang="ts"', 'lang="js"')
        spec = {
            "script_lang": "ts",
            "use_form": "useForm",
            "zod_schema": "z.object",
            "typed_schema": "toTypedSchema",
            "fields": ["username", "email", "password", "role", "terms", "bio"],
            "error_display": "errors",
        }
        result = validate_ast_structure(code, spec)
        assert result.score == 8.0
        assert "script_lang" in result.missing

    def test_errormessage_component_counts_as_error_display(self):
        """Using <ErrorMessage> instead of errors.field → still counts as error_display."""
        code = COMPLETE_COMPONENT.replace("errors.", "ERR_REMOVED.").replace(
            "</template>",
            "  <ErrorMessage name='username' />\n</template>"
        )
        spec = {
            "script_lang": "ts",
            "use_form": "useForm",
            "zod_schema": "z.object",
            "typed_schema": "toTypedSchema",
            "fields": ["username", "email", "password", "role", "terms", "bio"],
            "error_display": "errors",
        }
        result = validate_ast_structure(code, spec)
        assert "error_display" not in result.missing

    def test_returns_astresult_instance(self):
        """Return type is ASTResult."""
        result = validate_ast_structure(COMPLETE_COMPONENT, {})
        assert isinstance(result, ASTResult)


# ---------------------------------------------------------------------------
# validate_naming tests
# ---------------------------------------------------------------------------

class TestValidateNaming:
    """validate_naming: camelCase variable checks."""

    def test_camelcase_variables_score_one(self):
        """All variables in camelCase → score=1.0, no violations."""
        code = (
            "<script setup lang='ts'>\n"
            "const registrationSchema = z.object({})\n"
            "const { errors, handleSubmit } = useForm({})\n"
            "const onSubmit = handleSubmit(() => {})\n"
            "</script>"
        )
        result = validate_naming(code, {"variables": "camelCase"})
        assert result.score == 1.0
        assert result.follows_conventions is True
        assert len(result.violations) == 0

    def test_uppercase_variable_scores_zero(self):
        """Variable starting with uppercase → camelCase violation."""
        code = (
            "<script setup lang='ts'>\n"
            "const RegistrationSchema = z.object({})\n"
            "</script>"
        )
        result = validate_naming(code, {"variables": "camelCase"})
        assert result.score == 0.0
        assert result.follows_conventions is False
        assert any("RegistrationSchema" in v for v in result.violations)

    def test_underscore_prefix_variable_scores_zero(self):
        """Variable with underscore prefix → camelCase violation."""
        code = (
            "<script setup lang='ts'>\n"
            "const _privateVar = 'value'\n"
            "</script>"
        )
        result = validate_naming(code, {"variables": "camelCase"})
        assert result.score == 0.0
        assert result.follows_conventions is False

    def test_no_variables_scores_one(self):
        """No const/let/var declarations → nothing to violate → score=1.0."""
        code = "<script setup lang='ts'>\n</script>"
        result = validate_naming(code, {"variables": "camelCase"})
        assert result.score == 1.0
        assert result.follows_conventions is True

    def test_mixed_valid_invalid_scores_zero(self):
        """One valid, one invalid variable → overall score=0.0."""
        code = (
            "<script setup lang='ts'>\n"
            "const validName = 'ok'\n"
            "const InvalidName = 'bad'\n"
            "</script>"
        )
        result = validate_naming(code, {"variables": "camelCase"})
        assert result.score == 0.0
        assert result.follows_conventions is False

    def test_returns_naming_result_instance(self):
        """Return type is NamingResult."""
        result = validate_naming("", {"variables": "camelCase"})
        assert isinstance(result, NamingResult)

    def test_empty_conventions_no_violations(self):
        """Empty conventions dict → no checks → score=1.0."""
        code = "<script setup lang='ts'>\nconst SomeVar = 1\n</script>"
        result = validate_naming(code, {})
        assert result.score == 1.0


# ---------------------------------------------------------------------------
# Exception handling in creation test runner
# ---------------------------------------------------------------------------

def _make_veevalidate_fixture(tmp_path: Path) -> Path:
    """Create a minimal valid fixture directory for veevalidate-zod-form."""
    fixture_path = tmp_path / "veevalidate-zod-form"
    fixture_path.mkdir()

    (fixture_path / "prompt.md").write_text("Implement a registration form.")

    spec = {
        "target_file": "src/components/RegistrationForm.vue",
        "required_patterns": {
            "script_lang": "ts",
            "use_form": "useForm",
            "zod_schema": "z.object",
            "typed_schema": "toTypedSchema",
            "fields": ["username", "email", "password", "role", "terms", "bio"],
            "error_display": "errors",
        },
        "naming_conventions": {"variables": "camelCase"},
        "scoring": {"compilation": 0.5, "pattern_match": 0.4, "naming": 0.1},
    }
    (fixture_path / "validation_spec.json").write_text(json.dumps(spec))

    target_project = fixture_path / "target_project"
    components_dir = target_project / "src" / "components"
    components_dir.mkdir(parents=True)
    (components_dir / "RegistrationForm.vue").write_text(
        "<script setup lang='ts'>\n</script>\n<template>\n</template>"
    )

    return fixture_path


class TestVeeValidateRunnerExceptionHandling:
    """Ensure veevalidate_zod_form test runner handles validation exceptions gracefully."""

    @patch("src.creation.veevalidate_zod_form.test_runner.ollama_client")
    @patch("src.creation.veevalidate_zod_form.test_runner.validator")
    def test_ast_exception_handled_gracefully(self, mock_validator, mock_ollama, tmp_path):
        """When validate_ast_structure raises, returns degraded BenchmarkResult (no crash)."""
        from src.creation.veevalidate_zod_form.test_runner import CreationTest, BenchmarkResult
        from src.common.ollama_client import ChatResult
        from src.creation.veevalidate_zod_form.validator import CompilationResult, NamingResult

        mock_ollama.chat.return_value = ChatResult(
            response_text="<script setup lang='ts'></script>",
            duration_sec=5.0, tokens_generated=20, tokens_per_sec=25.0, success=True,
        )
        mock_validator.validate_compilation.return_value = CompilationResult(
            success=False, errors=["TS error"], warnings=[], duration_sec=1.0
        )
        mock_validator.validate_ast_structure.side_effect = Exception("regex parsing failed")
        mock_validator.validate_naming.return_value = NamingResult(
            follows_conventions=True, violations=[], score=1.0
        )

        result = CreationTest(
            model="test-model",
            fixture_path=_make_veevalidate_fixture(tmp_path)
        ).run(run_number=1)

        assert isinstance(result, BenchmarkResult)
        assert result.pattern_score == 0.0
        assert len(result.errors) > 0
        assert any("AST" in e for e in result.errors)

    @patch("src.creation.veevalidate_zod_form.test_runner.ollama_client")
    @patch("src.creation.veevalidate_zod_form.test_runner.validator")
    def test_naming_exception_handled_gracefully(self, mock_validator, mock_ollama, tmp_path):
        """When validate_naming raises, returns degraded BenchmarkResult (no crash)."""
        from src.creation.veevalidate_zod_form.test_runner import CreationTest, BenchmarkResult
        from src.common.ollama_client import ChatResult
        from src.creation.veevalidate_zod_form.validator import CompilationResult, ASTResult

        mock_ollama.chat.return_value = ChatResult(
            response_text="<script setup lang='ts'></script>",
            duration_sec=5.0, tokens_generated=20, tokens_per_sec=25.0, success=True,
        )
        mock_validator.validate_compilation.return_value = CompilationResult(
            success=True, errors=[], warnings=[], duration_sec=1.0
        )
        mock_validator.validate_ast_structure.return_value = ASTResult(
            score=6.0, missing=["fields"]
        )
        mock_validator.validate_naming.side_effect = Exception("naming regex failed")

        result = CreationTest(
            model="test-model",
            fixture_path=_make_veevalidate_fixture(tmp_path)
        ).run(run_number=2)

        assert isinstance(result, BenchmarkResult)
        assert result.naming_score == 0.0
        assert len(result.errors) > 0
        assert any("naming" in e.lower() for e in result.errors)
