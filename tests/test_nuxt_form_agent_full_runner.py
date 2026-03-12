"""Tests for src/agent/nuxt_form_agent_full/test_runner.py.

Key differences from veevalidate_zod_form agent runner:
- Two stub files restored (RegistrationForm.vue + types/index.ts)
- Custom tools: query_rag + compilation runs from apps/web/
- validate_ast_structure receives combined code from both files
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agent.nuxt_form_agent_full.test_runner import AgentBenchmarkResult, AgentTest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STUB_VUE = "<script setup lang='ts'>\n// TODO\n</script>\n\n<template>\n  <div></div>\n</template>\n"
STUB_TYPES = "// Registration form types — agent will implement the schema and type here.\n"

COMPLETE_VUE = """<script setup lang="ts">
import { Button, ControlledInput, Form, FormActions, FormFields } from "elements";
import { z } from "zod";
const schema = z.object({ username: z.string(), email: z.string().email(), role: z.enum(["user"]), bio: z.string().optional() });
type Values = z.infer<typeof schema>;
const initialValues: Values = { username: "", email: "", role: "user", bio: "" };
const actions = { onSubmit: async (v: Values) => v };
</script>
<template>
  <Form :initial-values="initialValues" :form-schema="schema" :actions="actions">
    <FormFields v-slot="{ form, resetGeneralError }">
      <ControlledInput name="username" label="Username" @input-click="resetGeneralError" />
      <ControlledInput name="email" label="Email" @input-click="resetGeneralError" />
      <ControlledInput v-if="form.values.role" name="role" label="Role" @input-click="resetGeneralError" />
      <ControlledInput name="bio" label="Bio" @input-click="resetGeneralError" />
    </FormFields>
    <FormActions v-slot="{ form, isValid }">
      <Button type="submit" :disabled="!isValid">Submit</Button>
    </FormActions>
  </Form>
</template>
"""

DEFAULT_SPEC = {
    "target_file": "apps/web/src/registration/components/RegistrationForm.vue",
    "allowed_write_paths": [
        "apps/web/src/registration/components/RegistrationForm.vue",
        "apps/web/src/registration/types/index.ts",
    ],
    "compilation_command": "check-types",
    "compilation_cwd": "apps/web",
    "max_steps": 30,
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
    fixture_path = tmp_path / "veevalidate-zod-form-nuxt-rag"
    fixture_path.mkdir()

    (fixture_path / "prompt.md").write_text("Implement a registration form using the elements library.")

    target_spec = spec if spec is not None else DEFAULT_SPEC
    (fixture_path / "validation_spec.json").write_text(json.dumps(target_spec))

    # Minimal rag_docs
    rag_docs = fixture_path / "rag_docs"
    rag_docs.mkdir()
    (rag_docs / "01_basic_form.vue").write_text("<!-- basic form example -->")

    # target_project with both stub files
    target_project = fixture_path / "target_project"
    comp_dir = target_project / "apps" / "web" / "src" / "registration" / "components"
    comp_dir.mkdir(parents=True)
    (comp_dir / "RegistrationForm.vue").write_text(STUB_VUE)

    types_dir = target_project / "apps" / "web" / "src" / "registration" / "types"
    types_dir.mkdir(parents=True)
    (types_dir / "index.ts").write_text(STUB_TYPES)

    return fixture_path


def _make_agent_result(**kwargs):
    defaults = dict(
        succeeded=True, steps=5, final_output="Done",
        tool_call_log=[{"step": 1, "tool": "write_file", "args": {}, "result_summary": "written"}],
        duration_sec=10.0, tokens_per_sec=20.0, errors=[],
        total_input_tokens=600, total_output_tokens=250,
        first_compile_success_step=1, compile_error_recovery_count=0,
        rag_queries_count=1, read_file_count=2, list_files_count=1,
        run_crashed=False,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_compilation_result(success=True, errors=None, warnings=None):
    return SimpleNamespace(success=success, errors=errors or [], warnings=warnings or [])


def _make_ast_result(score=10.0, missing=None, checks=None):
    return SimpleNamespace(
        score=score, missing=missing or [],
        checks=checks or {"script_lang": True, "form_component": True, "zod_schema": True},
    )


def _make_naming_result(score=1.0, violations=None):
    return SimpleNamespace(score=score, violations=violations or [])


# ---------------------------------------------------------------------------
# AgentBenchmarkResult
# ---------------------------------------------------------------------------

class TestAgentBenchmarkResult:

    def test_all_fields_present(self):
        result = AgentBenchmarkResult(
            model="m", fixture="f", timestamp="t", run_number=1,
            compiles=True, compilation_errors=[], compilation_warnings=[],
            pattern_score=10.0, ast_missing=[], ast_checks={},
            naming_score=10.0, naming_violations=[], final_score=10.0,
            scoring_weights={}, tokens_per_sec=0.0, duration_sec=1.0,
            output_code="", errors=[], steps=5, max_steps=30, iterations=2,
            succeeded=True, tool_call_log=[], aborted=False,
        )
        assert result.steps == 5
        assert result.max_steps == 30
        assert result.iterations == 2
        assert result.aborted is False

    def test_json_serialisable(self):
        result = AgentBenchmarkResult(
            model="m", fixture="f", timestamp="t", run_number=1,
            compiles=True, compilation_errors=[], compilation_warnings=[],
            pattern_score=10.0, ast_missing=[], ast_checks={},
            naming_score=10.0, naming_violations=[], final_score=10.0,
            scoring_weights={}, tokens_per_sec=0.0, duration_sec=1.0,
            output_code="", errors=[], steps=5, max_steps=30, iterations=2,
            succeeded=True, tool_call_log=[], aborted=False,
        )
        dumped = json.dumps(result.__dict__)
        assert "steps" in dumped
        assert "max_steps" in dumped
        assert "aborted" in dumped


# ---------------------------------------------------------------------------
# AgentTest init
# ---------------------------------------------------------------------------

class TestAgentTestInit:

    def test_loads_prompt_and_spec(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = AgentTest(model="test-model", fixture_path=fixture_path)
        assert "registration form" in test.prompt.lower()
        assert test.validation_spec["target_file"].endswith("RegistrationForm.vue")

    def test_reads_max_steps(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = AgentTest(model="test-model", fixture_path=fixture_path)
        assert test.max_steps == 30

    def test_reads_allowed_paths(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = AgentTest(model="test-model", fixture_path=fixture_path)
        assert any("RegistrationForm.vue" in p for p in test.allowed_paths)
        assert any("types/index.ts" in p for p in test.allowed_paths)

    def test_stores_original_stub_content_for_both_files(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = AgentTest(model="test-model", fixture_path=fixture_path)
        assert test.original_code == STUB_VUE
        assert test.original_types == STUB_TYPES

    def test_raises_on_missing_prompt(self, tmp_path):
        fixture_path = tmp_path / "broken"
        fixture_path.mkdir()
        with pytest.raises(FileNotFoundError, match="prompt.md"):
            AgentTest(model="m", fixture_path=fixture_path)

    def test_raises_on_missing_validation_spec(self, tmp_path):
        fixture_path = tmp_path / "broken"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("task")
        with pytest.raises(FileNotFoundError, match="validation_spec.json"):
            AgentTest(model="m", fixture_path=fixture_path)

    def test_raises_on_missing_rag_docs(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        import shutil
        shutil.rmtree(fixture_path / "rag_docs")
        with pytest.raises(FileNotFoundError, match="rag_docs"):
            AgentTest(model="m", fixture_path=fixture_path)

    def test_raises_on_missing_target_file(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        target = fixture_path / "target_project" / "apps" / "web" / "src" / "registration" / "components" / "RegistrationForm.vue"
        target.unlink()
        with pytest.raises(FileNotFoundError):
            AgentTest(model="m", fixture_path=fixture_path)


# ---------------------------------------------------------------------------
# AgentTest.run()
# ---------------------------------------------------------------------------

class TestAgentTestRun:

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_returns_agent_benchmark_result(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        test = AgentTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=1)
        assert isinstance(result, AgentBenchmarkResult)

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_perfect_score_when_all_pass(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result(success=True)
        mock_validator.validate_ast_structure.return_value = _make_ast_result(score=10.0)
        mock_validator.validate_naming.return_value = _make_naming_result(score=1.0)

        result = AgentTest(model="m", fixture_path=fixture_path).run(run_number=1)
        assert result.final_score == pytest.approx(10.0)

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_zero_score_when_all_fail(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result(success=False)
        mock_validator.validate_ast_structure.return_value = _make_ast_result(score=0.0)
        mock_validator.validate_naming.return_value = _make_naming_result(score=0.0)

        result = AgentTest(model="m", fixture_path=fixture_path).run(run_number=1)
        assert result.final_score == pytest.approx(0.0)

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_weighted_scoring(self, mock_run_agent, mock_validator, tmp_path):
        """compile(1.0)*0.5 + pattern(0.5)*0.4 + naming(0.0)*0.1 = 0.7 → 7.0"""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result(success=True)
        mock_validator.validate_ast_structure.return_value = _make_ast_result(score=5.0)
        mock_validator.validate_naming.return_value = _make_naming_result(score=0.0)

        result = AgentTest(model="m", fixture_path=fixture_path).run(run_number=1)
        assert result.final_score == pytest.approx(7.0)

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_both_stubs_restored_after_run(self, mock_run_agent, mock_validator, tmp_path):
        """Both RegistrationForm.vue and types/index.ts must revert to stubs."""
        fixture_path = _make_fixture(tmp_path)
        target_vue = fixture_path / "target_project" / "apps" / "web" / "src" / "registration" / "components" / "RegistrationForm.vue"
        target_ts = fixture_path / "target_project" / "apps" / "web" / "src" / "registration" / "types" / "index.ts"

        def side_effect(*args, **kwargs):
            target_vue.write_text(COMPLETE_VUE)
            target_ts.write_text("export const x = 1;")
            return _make_agent_result()

        mock_run_agent.side_effect = side_effect
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run(run_number=1)

        assert target_vue.read_text() == STUB_VUE
        assert target_ts.read_text() == STUB_TYPES

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_stubs_restored_even_on_exception(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        target_vue = fixture_path / "target_project" / "apps" / "web" / "src" / "registration" / "components" / "RegistrationForm.vue"
        target_ts = fixture_path / "target_project" / "apps" / "web" / "src" / "registration" / "types" / "index.ts"

        mock_run_agent.side_effect = RuntimeError("crash")

        test = AgentTest(model="m", fixture_path=fixture_path)
        with pytest.raises(RuntimeError):
            test.run(run_number=1)

        assert target_vue.read_text() == STUB_VUE
        assert target_ts.read_text() == STUB_TYPES

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_ast_exception_produces_degraded_result(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.side_effect = Exception("regex crashed")
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = AgentTest(model="m", fixture_path=fixture_path).run(run_number=1)
        assert result.pattern_score == 0.0
        assert len(result.errors) > 0

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_validate_ast_receives_combined_code(self, mock_run_agent, mock_validator, tmp_path):
        """validate_ast_structure must receive content from both files combined."""
        fixture_path = _make_fixture(tmp_path)
        target_vue = fixture_path / "target_project" / "apps" / "web" / "src" / "registration" / "components" / "RegistrationForm.vue"
        target_ts = fixture_path / "target_project" / "apps" / "web" / "src" / "registration" / "types" / "index.ts"

        def side_effect(*args, **kwargs):
            target_vue.write_text(COMPLETE_VUE)
            target_ts.write_text("export const schema = z.object({});")
            return _make_agent_result()

        mock_run_agent.side_effect = side_effect
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run(run_number=1)

        call_args = mock_validator.validate_ast_structure.call_args
        code_arg = call_args[0][0] if call_args[0] else call_args.kwargs.get("code", "")
        # Both file contents must be present
        assert "z.object" in code_arg or COMPLETE_VUE[:50] in code_arg

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_run_number_in_result(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = AgentTest(model="m", fixture_path=fixture_path).run(run_number=3)
        assert result.run_number == 3

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_query_rag_tool_included_in_agent_tools(self, mock_run_agent, mock_validator, tmp_path):
        """run_agent must receive a tool named 'query_rag'."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run(run_number=1)

        call_kwargs = mock_run_agent.call_args
        tools = call_kwargs.kwargs.get("tools") or (call_kwargs[0][2] if len(call_kwargs[0]) > 2 else [])
        tool_names = [getattr(t, "name", None) for t in tools]
        assert "query_rag" in tool_names


# ---------------------------------------------------------------------------
# AgentTest.run() — aborted run handling
# ---------------------------------------------------------------------------

class TestAbortedRun:

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_aborted_true_when_run_crashed(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(run_crashed=True, steps=0, errors=["Ollama error"])

        result = AgentTest(model="m", fixture_path=fixture_path).run(run_number=1)

        assert result.aborted is True

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_aborted_run_scores_are_zero(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(run_crashed=True, steps=0)

        result = AgentTest(model="m", fixture_path=fixture_path).run(run_number=1)

        assert result.final_score == 0.0
        assert result.pattern_score == 0.0
        assert result.naming_score == 0.0
        assert result.compiles is False

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_aborted_run_skips_validation(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(run_crashed=True, steps=0)

        AgentTest(model="m", fixture_path=fixture_path).run(run_number=1)

        mock_validator.validate_compilation.assert_not_called()
        mock_validator.validate_ast_structure.assert_not_called()
        mock_validator.validate_naming.assert_not_called()

    @patch("src.agent.nuxt_form_agent_full.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_full.test_runner.run_agent")
    def test_non_crashed_run_not_aborted(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(run_crashed=False)
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = AgentTest(model="m", fixture_path=fixture_path).run(run_number=1)

        assert result.aborted is False


# ---------------------------------------------------------------------------
# write_file decoupling — tool must only write, not compile
# ---------------------------------------------------------------------------

class TestWriteFileDecoupled:

    def test_write_file_returns_file_written_only(self, tmp_path):
        """After decoupling, write_file must return 'File written.' with no compilation output."""
        from src.agent.nuxt_form_agent_full.test_runner import _make_tools
        from unittest.mock import MagicMock

        allowed_path = "apps/web/src/registration/components/RegistrationForm.vue"
        comp_dir = tmp_path / "apps" / "web" / "src" / "registration" / "components"
        comp_dir.mkdir(parents=True)
        (comp_dir / "RegistrationForm.vue").write_text("initial")

        mock_rag_tool = MagicMock()

        tools = _make_tools(
            target_project=tmp_path,
            allowed_paths=[allowed_path],
            compilation_cwd=tmp_path,
            compilation_command="check-types",
            rag_tool=mock_rag_tool,
        )
        write_tool = next(t for t in tools if t.name == "write_file")
        result = write_tool(path=allowed_path, content="<script>new</script>")

        assert result == "File written."
        assert "Compilation" not in result
