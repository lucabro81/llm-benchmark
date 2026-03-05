"""Tests for src/creation/nuxt_form_creation/test_runner.py.

Key differences from standard CreationTest:
- target_project resolved via target_project_path in validation_spec.json
- compilation uses compilation_cwd + compilation_command (npm run check-types from apps/web)
- types/index.ts stub also saved/restored (defensive: shared target_project)
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.creation.nuxt_form_creation.test_runner import BenchmarkResult, CreationTest

STUB_VUE = "<script setup lang='ts'>\n// TODO\n</script>\n\n<template>\n  <div></div>\n</template>\n"
STUB_TYPES = "// types stub\n"

COMPLETE_VUE = """<script setup lang="ts">
import { ControlledInput, Form, FormActions, FormFields } from "elements";
import { z } from "zod";
const schema = z.object({ username: z.string(), email: z.string().email(), role: z.enum(["user"]), bio: z.string().optional() });
type Values = z.infer<typeof schema>;
const initialValues: Values = { username: "", email: "", role: "user", bio: "" };
const actions = { onSubmit: async (v: Values) => v };
</script>
<template>
  <Form :initial-values="initialValues" :form-schema="schema" :actions="actions">
    <FormFields v-slot="{ form, resetGeneralError }">
      <ControlledInput name="username" @input-click="resetGeneralError" />
      <ControlledInput name="email" @input-click="resetGeneralError" />
      <ControlledInput v-if="form.values.role" name="role" @input-click="resetGeneralError" />
      <ControlledInput name="bio" @input-click="resetGeneralError" />
    </FormFields>
    <FormActions v-slot="{ form, isValid }">
      <button type="submit" :disabled="!isValid">OK</button>
    </FormActions>
  </Form>
</template>
"""

DEFAULT_SPEC = {
    "target_project_path": "../shared_target_project",
    "target_file": "apps/web/src/registration/components/RegistrationForm.vue",
    "compilation_cwd": "apps/web",
    "compilation_command": "check-types",
    "required_patterns": {
        "script_lang": "ts",
        "form_component": "<Form",
        "controlled_components": ["ControlledInput", "ControlledRadioGroup", "ControlledCheckbox", "ControlledTextarea"],
        "conditional_rendering": "v-if",
        "zod_schema": "z.object",
        "required_fields": ["username", "email", "role", "bio"],
        "conditional_fields": ["newsletter", "frequency", "otherInfo"],
    },
    "naming_conventions": {"variables": "camelCase"},
    "scoring": {"compilation": 0.5, "pattern_match": 0.4, "naming": 0.1},
}


def _make_fixture(tmp_path: Path, spec=None) -> Path:
    """Create fixture dir + separate shared target_project."""
    # Shared target project (sibling of fixture dir)
    shared_tp = tmp_path / "shared_target_project"
    comp_dir = shared_tp / "apps" / "web" / "src" / "registration" / "components"
    comp_dir.mkdir(parents=True)
    (comp_dir / "RegistrationForm.vue").write_text(STUB_VUE)

    types_dir = shared_tp / "apps" / "web" / "src" / "registration" / "types"
    types_dir.mkdir(parents=True)
    (types_dir / "index.ts").write_text(STUB_TYPES)

    # Fixture dir
    fixture_path = tmp_path / "nuxt-form-creation"
    fixture_path.mkdir()
    (fixture_path / "prompt.md").write_text("Implement a registration form.")
    target_spec = spec if spec is not None else DEFAULT_SPEC
    (fixture_path / "validation_spec.json").write_text(json.dumps(target_spec))

    return fixture_path


def _make_chat_result(response="```vue\n" + COMPLETE_VUE + "\n```"):
    return SimpleNamespace(
        response_text=response,
        tokens_per_sec=30.0,
        duration_sec=5.0,
    )


def _make_compilation_result(success=True, errors=None, warnings=None):
    return SimpleNamespace(success=success, errors=errors or [], warnings=warnings or [], duration_sec=1.0)


def _make_ast_result(score=10.0, missing=None, checks=None):
    return SimpleNamespace(score=score, missing=missing or [], checks=checks or {"script_lang": True})


def _make_naming_result(score=1.0, violations=None):
    return SimpleNamespace(score=score, violations=violations or [], follows_conventions=score == 1.0)


# ---------------------------------------------------------------------------
# BenchmarkResult
# ---------------------------------------------------------------------------

class TestBenchmarkResult:

    def test_all_fields_present(self):
        r = BenchmarkResult(
            model="m", fixture="f", timestamp="t", run_number=1,
            compiles=True, compilation_errors=[], compilation_warnings=[],
            pattern_score=10.0, ast_missing=[], ast_checks={},
            naming_score=10.0, naming_violations=[], final_score=10.0,
            scoring_weights={}, tokens_per_sec=0.0, duration_sec=1.0,
            output_code="", errors=[],
        )
        assert r.final_score == 10.0

    def test_json_serialisable(self):
        r = BenchmarkResult(
            model="m", fixture="f", timestamp="t", run_number=1,
            compiles=True, compilation_errors=[], compilation_warnings=[],
            pattern_score=10.0, ast_missing=[], ast_checks={},
            naming_score=10.0, naming_violations=[], final_score=10.0,
            scoring_weights={}, tokens_per_sec=0.0, duration_sec=1.0,
            output_code="", errors=[],
        )
        import json as _json
        assert "final_score" in _json.dumps(r.__dict__)


# ---------------------------------------------------------------------------
# CreationTest init
# ---------------------------------------------------------------------------

class TestCreationTestInit:

    def test_loads_prompt_and_spec(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = CreationTest(model="test-model", fixture_path=fixture_path)
        assert "registration form" in test.prompt_template.lower()
        assert test.validation_spec["target_file"].endswith("RegistrationForm.vue")

    def test_resolves_target_project_from_spec(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = CreationTest(model="test-model", fixture_path=fixture_path)
        assert test.target_project == (tmp_path / "shared_target_project").resolve()

    def test_reads_compilation_config(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = CreationTest(model="test-model", fixture_path=fixture_path)
        assert test._compilation_command == "check-types"
        assert test._compilation_cwd.name == "web"

    def test_stores_original_stub(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = CreationTest(model="test-model", fixture_path=fixture_path)
        assert test.original_code == STUB_VUE

    def test_raises_on_missing_prompt(self, tmp_path):
        fixture_path = tmp_path / "broken"
        fixture_path.mkdir()
        with pytest.raises(FileNotFoundError, match="prompt.md"):
            CreationTest(model="m", fixture_path=fixture_path)

    def test_raises_on_missing_spec(self, tmp_path):
        fixture_path = tmp_path / "broken"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("task")
        with pytest.raises(FileNotFoundError, match="validation_spec.json"):
            CreationTest(model="m", fixture_path=fixture_path)

    def test_raises_when_target_project_not_found(self, tmp_path):
        fixture_path = tmp_path / "nuxt-form-creation"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("task")
        spec = dict(DEFAULT_SPEC)
        spec["target_project_path"] = "../nonexistent"
        (fixture_path / "validation_spec.json").write_text(json.dumps(spec))
        with pytest.raises(FileNotFoundError):
            CreationTest(model="m", fixture_path=fixture_path)

    def test_raises_when_target_file_not_found(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        # Remove the stub file
        target = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "registration" / "components" / "RegistrationForm.vue"
        target.unlink()
        with pytest.raises(FileNotFoundError):
            CreationTest(model="m", fixture_path=fixture_path)

    def test_falls_back_to_local_target_project_when_no_override(self, tmp_path):
        """If target_project_path not in spec, falls back to fixture_path/target_project."""
        spec = dict(DEFAULT_SPEC)
        del spec["target_project_path"]

        fixture_path = tmp_path / "nuxt-form-creation"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("task")
        (fixture_path / "validation_spec.json").write_text(json.dumps(spec))

        # Create local target_project
        comp_dir = fixture_path / "target_project" / "apps" / "web" / "src" / "registration" / "components"
        comp_dir.mkdir(parents=True)
        (comp_dir / "RegistrationForm.vue").write_text(STUB_VUE)

        test = CreationTest(model="m", fixture_path=fixture_path)
        assert test.target_project == fixture_path / "target_project"


# ---------------------------------------------------------------------------
# CreationTest.run()
# ---------------------------------------------------------------------------

class TestCreationTestRun:

    @patch("src.creation.nuxt_form_creation.test_runner.validator")
    @patch("src.creation.nuxt_form_creation.test_runner.ollama_client")
    def test_returns_benchmark_result(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_ollama.chat.return_value = _make_chat_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = CreationTest(model="m", fixture_path=fixture_path).run(run_number=1)
        assert isinstance(result, BenchmarkResult)

    @patch("src.creation.nuxt_form_creation.test_runner.validator")
    @patch("src.creation.nuxt_form_creation.test_runner.ollama_client")
    def test_perfect_score_when_all_pass(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_ollama.chat.return_value = _make_chat_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result(success=True)
        mock_validator.validate_ast_structure.return_value = _make_ast_result(score=10.0)
        mock_validator.validate_naming.return_value = _make_naming_result(score=1.0)

        result = CreationTest(model="m", fixture_path=fixture_path).run()
        assert result.final_score == pytest.approx(10.0)

    @patch("src.creation.nuxt_form_creation.test_runner.validator")
    @patch("src.creation.nuxt_form_creation.test_runner.ollama_client")
    def test_zero_score_when_all_fail(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_ollama.chat.return_value = _make_chat_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result(success=False)
        mock_validator.validate_ast_structure.return_value = _make_ast_result(score=0.0)
        mock_validator.validate_naming.return_value = _make_naming_result(score=0.0)

        result = CreationTest(model="m", fixture_path=fixture_path).run()
        assert result.final_score == pytest.approx(0.0)

    @patch("src.creation.nuxt_form_creation.test_runner.validator")
    @patch("src.creation.nuxt_form_creation.test_runner.ollama_client")
    def test_weighted_scoring(self, mock_ollama, mock_validator, tmp_path):
        """compile(1.0)*0.5 + pattern(0.5)*0.4 + naming(0.0)*0.1 = 0.7 → 7.0"""
        fixture_path = _make_fixture(tmp_path)
        mock_ollama.chat.return_value = _make_chat_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result(success=True)
        mock_validator.validate_ast_structure.return_value = _make_ast_result(score=5.0)
        mock_validator.validate_naming.return_value = _make_naming_result(score=0.0)

        result = CreationTest(model="m", fixture_path=fixture_path).run()
        assert result.final_score == pytest.approx(7.0)

    @patch("src.creation.nuxt_form_creation.test_runner.validator")
    @patch("src.creation.nuxt_form_creation.test_runner.ollama_client")
    def test_stub_restored_after_run(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        target_vue = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "registration" / "components" / "RegistrationForm.vue"

        def side_effect(*args, **kwargs):
            target_vue.write_text(COMPLETE_VUE)
            return _make_chat_result(response=COMPLETE_VUE)

        mock_ollama.chat.side_effect = side_effect
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        CreationTest(model="m", fixture_path=fixture_path).run()
        assert target_vue.read_text() == STUB_VUE

    @patch("src.creation.nuxt_form_creation.test_runner.validator")
    @patch("src.creation.nuxt_form_creation.test_runner.ollama_client")
    def test_stub_restored_on_exception(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        target_vue = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "registration" / "components" / "RegistrationForm.vue"
        mock_ollama.chat.side_effect = RuntimeError("crash")

        test = CreationTest(model="m", fixture_path=fixture_path)
        with pytest.raises(RuntimeError):
            test.run()

        assert target_vue.read_text() == STUB_VUE

    @patch("src.creation.nuxt_form_creation.test_runner.validator")
    @patch("src.creation.nuxt_form_creation.test_runner.ollama_client")
    def test_run_number_in_result(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_ollama.chat.return_value = _make_chat_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = CreationTest(model="m", fixture_path=fixture_path).run(run_number=3)
        assert result.run_number == 3

    @patch("src.creation.nuxt_form_creation.test_runner.validator")
    @patch("src.creation.nuxt_form_creation.test_runner.ollama_client")
    def test_ast_exception_produces_degraded_result(self, mock_ollama, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_ollama.chat.return_value = _make_chat_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.side_effect = Exception("crash")
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = CreationTest(model="m", fixture_path=fixture_path).run()
        assert result.pattern_score == 0.0
        assert len(result.errors) > 0
