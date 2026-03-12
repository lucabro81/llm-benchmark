"""Tests for src/agent/nuxt_form_agent_guided/test_runner.py.

Key differences from nuxt-rag AgentTest:
- target_project resolved via target_project_path in validation_spec.json
- Tools: ONLY write_file + run_compilation (no read_file, no list_files, no query_rag)
- max_steps: 10
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agent.nuxt_form_agent_guided.test_runner import AgentBenchmarkResult, AgentTest

STUB_VUE = "<script setup lang='ts'>\n// TODO\n</script>\n\n<template>\n  <div></div>\n</template>\n"
STUB_TYPES = "// Registration form types — agent will implement the schema and type here.\n"

DEFAULT_SPEC = {
    "target_project_path": "../shared_target_project",
    "target_file": "apps/web/src/registration/components/RegistrationForm.vue",
    "allowed_write_paths": [
        "apps/web/src/registration/components/RegistrationForm.vue",
        "apps/web/src/registration/types/index.ts",
    ],
    "compilation_cwd": "apps/web",
    "compilation_command": "check-types",
    "max_steps": 10,
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
    shared_tp = tmp_path / "shared_target_project"
    comp_dir = shared_tp / "apps" / "web" / "src" / "registration" / "components"
    comp_dir.mkdir(parents=True)
    (comp_dir / "RegistrationForm.vue").write_text(STUB_VUE)
    types_dir = shared_tp / "apps" / "web" / "src" / "registration" / "types"
    types_dir.mkdir(parents=True)
    (types_dir / "index.ts").write_text(STUB_TYPES)

    fixture_path = tmp_path / "nuxt-form-agent-guided"
    fixture_path.mkdir()
    (fixture_path / "prompt.md").write_text("Implement a registration form.")
    target_spec = spec if spec is not None else DEFAULT_SPEC
    (fixture_path / "validation_spec.json").write_text(json.dumps(target_spec))
    return fixture_path


def _make_agent_result(**kwargs):
    defaults = dict(
        succeeded=True, steps=3, final_output="Done",
        tool_call_log=[{"step": 1, "tool": "write_file", "args": {}, "result_summary": "written"}],
        duration_sec=8.0, tokens_per_sec=25.0, errors=[],
        total_input_tokens=400, total_output_tokens=150,
        first_compile_success_step=1, compile_error_recovery_count=0,
        rag_queries_count=0, read_file_count=0, list_files_count=0,
        run_crashed=False,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_compilation_result(success=True, errors=None, warnings=None):
    return SimpleNamespace(success=success, errors=errors or [], warnings=warnings or [])


def _make_ast_result(score=10.0, missing=None, checks=None):
    return SimpleNamespace(score=score, missing=missing or [], checks=checks or {"script_lang": True})


def _make_naming_result(score=1.0, violations=None):
    return SimpleNamespace(score=score, violations=violations or [])


# ---------------------------------------------------------------------------
# AgentBenchmarkResult
# ---------------------------------------------------------------------------

class TestAgentBenchmarkResult:

    def test_all_fields_present(self):
        r = AgentBenchmarkResult(
            model="m", fixture="f", timestamp="t", run_number=1,
            compiles=True, compilation_errors=[], compilation_warnings=[],
            pattern_score=10.0, ast_missing=[], ast_checks={},
            naming_score=10.0, naming_violations=[], final_score=10.0,
            scoring_weights={}, tokens_per_sec=0.0, duration_sec=1.0,
            output_code="", errors=[], steps=3, max_steps=10, iterations=2,
            succeeded=True, tool_call_log=[], aborted=False,
        )
        assert r.max_steps == 10
        assert r.aborted is False


# ---------------------------------------------------------------------------
# AgentTest init
# ---------------------------------------------------------------------------

class TestAgentTestInit:

    def test_loads_prompt_and_spec(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = AgentTest(model="test-model", fixture_path=fixture_path)
        assert "registration form" in test.prompt.lower()
        assert test.validation_spec["target_file"].endswith("RegistrationForm.vue")

    def test_resolves_target_project_from_spec(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = AgentTest(model="test-model", fixture_path=fixture_path)
        assert test.target_project == (tmp_path / "shared_target_project").resolve()

    def test_reads_max_steps(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        assert AgentTest(model="m", fixture_path=fixture_path).max_steps == 10

    def test_raises_on_missing_prompt(self, tmp_path):
        fixture_path = tmp_path / "broken"
        fixture_path.mkdir()
        with pytest.raises(FileNotFoundError, match="prompt.md"):
            AgentTest(model="m", fixture_path=fixture_path)

    def test_raises_when_target_project_not_found(self, tmp_path):
        fixture_path = tmp_path / "nuxt-form-agent-guided"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("task")
        spec = dict(DEFAULT_SPEC)
        spec["target_project_path"] = "../nonexistent"
        (fixture_path / "validation_spec.json").write_text(json.dumps(spec))
        with pytest.raises(FileNotFoundError):
            AgentTest(model="m", fixture_path=fixture_path)


# ---------------------------------------------------------------------------
# AgentTest.run() — tool composition
# ---------------------------------------------------------------------------

class TestAgentTestTools:

    @patch("src.agent.nuxt_form_agent_guided.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_guided.test_runner.run_agent")
    def test_no_query_rag_in_tools(self, mock_run_agent, mock_validator, tmp_path):
        """Guided agent must NOT have query_rag tool."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run()

        tools = mock_run_agent.call_args.kwargs.get("tools") or mock_run_agent.call_args[0][2]
        tool_names = [getattr(t, "name", None) for t in tools]
        assert "query_rag" not in tool_names

    @patch("src.agent.nuxt_form_agent_guided.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_guided.test_runner.run_agent")
    def test_no_read_file_in_tools(self, mock_run_agent, mock_validator, tmp_path):
        """Guided agent must NOT have read_file tool."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run()

        tools = mock_run_agent.call_args.kwargs.get("tools") or mock_run_agent.call_args[0][2]
        tool_names = [getattr(t, "name", None) for t in tools]
        assert "read_file" not in tool_names

    @patch("src.agent.nuxt_form_agent_guided.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_guided.test_runner.run_agent")
    def test_no_list_files_in_tools(self, mock_run_agent, mock_validator, tmp_path):
        """Guided agent must NOT have list_files tool."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run()

        tools = mock_run_agent.call_args.kwargs.get("tools") or mock_run_agent.call_args[0][2]
        tool_names = [getattr(t, "name", None) for t in tools]
        assert "list_files" not in tool_names

    @patch("src.agent.nuxt_form_agent_guided.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_guided.test_runner.run_agent")
    def test_has_write_file_and_run_compilation(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run()

        tools = mock_run_agent.call_args.kwargs.get("tools") or mock_run_agent.call_args[0][2]
        tool_names = [getattr(t, "name", None) for t in tools]
        assert "write_file" in tool_names
        assert "run_compilation" in tool_names


# ---------------------------------------------------------------------------
# AgentTest.run() — scoring + restoration
# ---------------------------------------------------------------------------

class TestAgentTestRun:

    @patch("src.agent.nuxt_form_agent_guided.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_guided.test_runner.run_agent")
    def test_returns_agent_benchmark_result(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = AgentTest(model="m", fixture_path=fixture_path).run()
        assert isinstance(result, AgentBenchmarkResult)

    @patch("src.agent.nuxt_form_agent_guided.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_guided.test_runner.run_agent")
    def test_perfect_score(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result(success=True)
        mock_validator.validate_ast_structure.return_value = _make_ast_result(score=10.0)
        mock_validator.validate_naming.return_value = _make_naming_result(score=1.0)

        result = AgentTest(model="m", fixture_path=fixture_path).run()
        assert result.final_score == pytest.approx(10.0)

    @patch("src.agent.nuxt_form_agent_guided.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_guided.test_runner.run_agent")
    def test_both_stubs_restored_after_run(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        target_vue = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "registration" / "components" / "RegistrationForm.vue"
        target_ts = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "registration" / "types" / "index.ts"

        def side_effect(*args, **kwargs):
            target_vue.write_text("<script>changed</script>")
            target_ts.write_text("export const x = 1;")
            return _make_agent_result()

        mock_run_agent.side_effect = side_effect
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        AgentTest(model="m", fixture_path=fixture_path).run()
        assert target_vue.read_text() == STUB_VUE
        assert target_ts.read_text() == STUB_TYPES

    @patch("src.agent.nuxt_form_agent_guided.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_guided.test_runner.run_agent")
    def test_stubs_restored_on_exception(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        target_vue = tmp_path / "shared_target_project" / "apps" / "web" / "src" / "registration" / "components" / "RegistrationForm.vue"
        mock_run_agent.side_effect = RuntimeError("crash")

        test = AgentTest(model="m", fixture_path=fixture_path)
        with pytest.raises(RuntimeError):
            test.run()

        assert target_vue.read_text() == STUB_VUE


# ---------------------------------------------------------------------------
# AgentTest.run() — aborted run handling
# ---------------------------------------------------------------------------

class TestAbortedRun:

    @patch("src.agent.nuxt_form_agent_guided.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_guided.test_runner.run_agent")
    def test_aborted_true_when_run_crashed(self, mock_run_agent, mock_validator, tmp_path):
        """run_crashed=True in agent result must produce aborted=True in benchmark result."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(run_crashed=True, steps=0, errors=["Ollama error"])

        result = AgentTest(model="m", fixture_path=fixture_path).run()

        assert result.aborted is True

    @patch("src.agent.nuxt_form_agent_guided.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_guided.test_runner.run_agent")
    def test_aborted_run_scores_are_zero(self, mock_run_agent, mock_validator, tmp_path):
        """Aborted run must have all scores = 0 and compiles = False."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(run_crashed=True, steps=0, errors=["Ollama error"])

        result = AgentTest(model="m", fixture_path=fixture_path).run()

        assert result.final_score == 0.0
        assert result.pattern_score == 0.0
        assert result.naming_score == 0.0
        assert result.compiles is False

    @patch("src.agent.nuxt_form_agent_guided.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_guided.test_runner.run_agent")
    def test_aborted_run_skips_validation(self, mock_run_agent, mock_validator, tmp_path):
        """Validator must NOT be called when run is aborted."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(run_crashed=True, steps=0)

        AgentTest(model="m", fixture_path=fixture_path).run()

        mock_validator.validate_compilation.assert_not_called()
        mock_validator.validate_ast_structure.assert_not_called()
        mock_validator.validate_naming.assert_not_called()

    @patch("src.agent.nuxt_form_agent_guided.test_runner.validator")
    @patch("src.agent.nuxt_form_agent_guided.test_runner.run_agent")
    def test_non_crashed_run_not_aborted(self, mock_run_agent, mock_validator, tmp_path):
        """Normal run (run_crashed=False) must have aborted=False."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(run_crashed=False)
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        result = AgentTest(model="m", fixture_path=fixture_path).run()

        assert result.aborted is False


# ---------------------------------------------------------------------------
# write_file decoupling — tool must only write, not compile
# ---------------------------------------------------------------------------

class TestWriteFileDecoupled:

    def test_write_file_returns_file_written_only(self, tmp_path):
        """After decoupling, write_file must return 'File written.' with no compilation output."""
        from src.agent.nuxt_form_agent_guided.test_runner import _make_tools

        allowed_path = "apps/web/src/registration/components/RegistrationForm.vue"
        comp_dir = tmp_path / "apps" / "web" / "src" / "registration" / "components"
        comp_dir.mkdir(parents=True)
        (comp_dir / "RegistrationForm.vue").write_text("initial")

        tools = _make_tools(
            target_project=tmp_path,
            allowed_paths=[allowed_path],
            compilation_cwd=tmp_path,
            compilation_command="check-types",
        )
        write_tool = next(t for t in tools if t.name == "write_file")
        result = write_tool(path=allowed_path, content="<script>new</script>")

        assert result == "File written."
        assert "Compilation" not in result
