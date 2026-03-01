"""Tests for src/agent/ts_bugfix/test_runner.py — AgentTest orchestrator.

TDD Red phase: all tests fail until test_runner.py is implemented.

Mocks used:
- src.agent.ts_bugfix.test_runner.run_agent  → AgentRunResult-like SimpleNamespace
- src.agent.ts_bugfix.test_runner.validator  → module mock with validate_* methods
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agent.ts_bugfix.test_runner import AgentBenchmarkResult, AgentTest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BUGGY_VUE = "<script setup lang='ts'>\n// buggy code\n</script>"
FIXED_VUE = "<script setup lang='ts'>\nimport { computed } from 'vue'\ninterface ButtonProps { label: string; count: number }\nconst props = defineProps<ButtonProps>()\n</script>"

DEFAULT_SPEC = {
    "target_file": "src/components/BuggyComponent.vue",
    "allowed_write_paths": ["src/components/BuggyComponent.vue"],
    "max_steps": 5,
    "required_patterns": {
        "interfaces": ["ButtonProps"],
        "type_annotations": ["defineProps<ButtonProps>"],
        "script_lang": "ts",
    },
    "naming_conventions": {
        "interfaces": "PascalCase",
        "props_interface_suffix": "Props",
    },
    "scoring": {"compilation": 0.5, "pattern_match": 0.4, "naming": 0.1},
}


def _make_fixture(tmp_path, spec=None) -> Path:
    """Create a minimal valid agent fixture directory."""
    fixture_path = tmp_path / "ts-bugfix"
    fixture_path.mkdir()

    (fixture_path / "prompt.md").write_text("Fix TypeScript errors in BuggyComponent.vue")

    target_spec = spec if spec is not None else DEFAULT_SPEC
    (fixture_path / "validation_spec.json").write_text(json.dumps(target_spec))

    target_project = fixture_path / "target_project"
    comp_dir = target_project / "src" / "components"
    comp_dir.mkdir(parents=True)
    (comp_dir / "BuggyComponent.vue").write_text(BUGGY_VUE)

    return fixture_path


def _make_agent_result(**kwargs):
    """Build a SimpleNamespace mimicking AgentRunResult."""
    defaults = dict(
        succeeded=True,
        steps=3,
        final_output="Done",
        tool_call_log=[{"step": 1, "tool": "read_file", "args": {}, "result_summary": "content"}],
        duration_sec=5.0,
        tokens_per_sec=30.0,
        errors=[],
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_compilation_result(success=True, errors=None, warnings=None):
    return SimpleNamespace(
        success=success,
        errors=errors or [],
        warnings=warnings or [],
    )


def _make_ast_result(score=8.0, missing=None, checks=None):
    return SimpleNamespace(
        score=score,
        missing=missing or [],
        checks=checks or {"interfaces": True, "type_annotations": True},
    )


def _make_naming_result(score=1.0, violations=None):
    return SimpleNamespace(
        score=score,
        violations=violations or [],
    )


# ---------------------------------------------------------------------------
# AgentBenchmarkResult dataclass
# ---------------------------------------------------------------------------

class TestAgentBenchmarkResult:
    def test_all_expected_fields_present(self):
        result = AgentBenchmarkResult(
            model="test-model",
            fixture="ts-bugfix",
            timestamp="2026-01-01T00:00:00",
            run_number=1,
            compiles=True,
            compilation_errors=[],
            compilation_warnings=[],
            pattern_score=8.0,
            ast_missing=[],
            ast_checks={},
            naming_score=10.0,
            naming_violations=[],
            final_score=8.5,
            scoring_weights={"compilation": 0.5, "pattern_match": 0.4, "naming": 0.1},
            tokens_per_sec=30.0,
            duration_sec=5.0,
            output_code="...",
            errors=[],
            steps=3,
            max_steps=5,
            iterations=1,
            succeeded=True,
            tool_call_log=[],
        )
        assert result.steps == 3
        assert result.iterations == 1
        assert result.succeeded is True
        assert result.tool_call_log == []

    def test_dict_is_json_serialisable(self):
        result = AgentBenchmarkResult(
            model="m", fixture="f", timestamp="t", run_number=1,
            compiles=True, compilation_errors=[], compilation_warnings=[],
            pattern_score=8.0, ast_missing=[], ast_checks={},
            naming_score=10.0, naming_violations=[], final_score=8.5,
            scoring_weights={}, tokens_per_sec=0.0, duration_sec=1.0,
            output_code="", errors=[], steps=2, max_steps=5, iterations=0,
            succeeded=True, tool_call_log=[],
        )
        import json
        dumped = json.dumps(result.__dict__)
        assert "steps" in dumped
        assert "iterations" in dumped
        assert "succeeded" in dumped
        assert "tool_call_log" in dumped

    def test_agent_fields_present_in_dict(self):
        result = AgentBenchmarkResult(
            model="m", fixture="f", timestamp="t", run_number=1,
            compiles=True, compilation_errors=[], compilation_warnings=[],
            pattern_score=8.0, ast_missing=[], ast_checks={},
            naming_score=10.0, naming_violations=[], final_score=8.5,
            scoring_weights={}, tokens_per_sec=0.0, duration_sec=1.0,
            output_code="", errors=[], steps=2, max_steps=5, iterations=0,
            succeeded=True, tool_call_log=[{"step": 1, "tool": "read_file"}],
        )
        d = result.__dict__
        assert "steps" in d
        assert "max_steps" in d
        assert "iterations" in d
        assert "succeeded" in d
        assert "tool_call_log" in d


# ---------------------------------------------------------------------------
# AgentTest init
# ---------------------------------------------------------------------------

class TestAgentTestInit:
    def test_loads_prompt_and_spec(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = AgentTest(model="test-model", fixture_path=fixture_path)

        assert "Fix TypeScript errors" in test.prompt
        assert test.validation_spec["target_file"] == "src/components/BuggyComponent.vue"
        assert test.fixture_name == "ts-bugfix"

    def test_reads_max_steps_from_spec(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = AgentTest(model="test-model", fixture_path=fixture_path)

        assert test.max_steps == 5

    def test_reads_allowed_paths_from_spec(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = AgentTest(model="test-model", fixture_path=fixture_path)

        assert "src/components/BuggyComponent.vue" in test.allowed_paths

    def test_allowed_paths_defaults_to_target_file_if_missing_from_spec(self, tmp_path):
        spec = dict(DEFAULT_SPEC)
        del spec["allowed_write_paths"]
        fixture_path = _make_fixture(tmp_path, spec=spec)
        test = AgentTest(model="test-model", fixture_path=fixture_path)

        assert test.allowed_paths == ["src/components/BuggyComponent.vue"]

    def test_stores_original_buggy_code(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        test = AgentTest(model="test-model", fixture_path=fixture_path)

        assert test.original_code == BUGGY_VUE

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

    def test_raises_on_missing_target_project(self, tmp_path):
        fixture_path = tmp_path / "broken"
        fixture_path.mkdir()
        (fixture_path / "prompt.md").write_text("task")
        (fixture_path / "validation_spec.json").write_text(json.dumps(DEFAULT_SPEC))
        # no target_project directory
        with pytest.raises(FileNotFoundError, match="target_project"):
            AgentTest(model="m", fixture_path=fixture_path)

    def test_raises_on_missing_target_file(self, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        # Remove the target file
        (fixture_path / "target_project" / "src" / "components" / "BuggyComponent.vue").unlink()
        with pytest.raises(FileNotFoundError):
            AgentTest(model="m", fixture_path=fixture_path)


# ---------------------------------------------------------------------------
# AgentTest.run()
# ---------------------------------------------------------------------------

class TestAgentTestRun:
    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_returns_agent_benchmark_result(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        test = AgentTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=1)

        assert isinstance(result, AgentBenchmarkResult)

    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_result_contains_steps_and_succeeded(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result(steps=3, succeeded=True)
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        test = AgentTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=1)

        assert result.steps == 3
        assert result.succeeded is True

    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_iterations_counts_run_compilation_calls(self, mock_run_agent, mock_validator, tmp_path):
        """iterations = number of run_compilation entries in tool_call_log."""
        fixture_path = _make_fixture(tmp_path)
        log = [
            {"step": 1, "tool": "read_file", "args": {}, "result_summary": "..."},
            {"step": 2, "tool": "write_file", "args": {}, "result_summary": "OK"},
            {"step": 3, "tool": "run_compilation", "args": {}, "result_summary": "Compilation succeeded."},
        ]
        mock_run_agent.return_value = _make_agent_result(steps=3, tool_call_log=log)
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        test = AgentTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=1)

        assert result.iterations == 1

    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_perfect_score_when_all_checks_pass(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result(success=True)
        mock_validator.validate_ast_structure.return_value = _make_ast_result(score=10.0)
        mock_validator.validate_naming.return_value = _make_naming_result(score=1.0)

        test = AgentTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=1)

        assert result.final_score == pytest.approx(10.0)
        assert result.compiles is True

    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_zero_score_when_compilation_fails(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result(
            success=False, errors=["TS2304: Cannot find name 'computed'"]
        )
        mock_validator.validate_ast_structure.return_value = _make_ast_result(score=0.0)
        mock_validator.validate_naming.return_value = _make_naming_result(score=0.0)

        test = AgentTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=1)

        assert result.compiles is False
        assert result.compilation_errors == ["TS2304: Cannot find name 'computed'"]

    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_weighted_scoring_calculation(self, mock_run_agent, mock_validator, tmp_path):
        """Score = (1.0 * 0.5 + 0.5 * 0.4 + 0.0 * 0.1) * 10 = 7.0"""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result(success=True)
        mock_validator.validate_ast_structure.return_value = _make_ast_result(score=5.0)
        mock_validator.validate_naming.return_value = _make_naming_result(score=0.0)

        test = AgentTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=1)

        assert result.final_score == pytest.approx(7.0)

    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_original_file_restored_after_successful_run(self, mock_run_agent, mock_validator, tmp_path):
        """Target file must revert to original buggy state after run."""
        fixture_path = _make_fixture(tmp_path)
        target_file = fixture_path / "target_project" / "src" / "components" / "BuggyComponent.vue"

        def side_effect(*args, **kwargs):
            # Simulate agent writing the fixed version
            target_file.write_text(FIXED_VUE)
            return _make_agent_result()

        mock_run_agent.side_effect = side_effect
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        test = AgentTest(model="test-model", fixture_path=fixture_path)
        test.run(run_number=1)

        assert target_file.read_text() == BUGGY_VUE

    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_original_file_restored_even_on_exception(self, mock_run_agent, mock_validator, tmp_path):
        """File restoration must happen in finally block."""
        fixture_path = _make_fixture(tmp_path)
        target_file = fixture_path / "target_project" / "src" / "components" / "BuggyComponent.vue"

        mock_run_agent.side_effect = RuntimeError("unexpected crash")
        mock_validator.validate_compilation.return_value = _make_compilation_result()

        test = AgentTest(model="test-model", fixture_path=fixture_path)

        with pytest.raises(RuntimeError):
            test.run(run_number=1)

        assert target_file.read_text() == BUGGY_VUE

    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_ast_exception_produces_degraded_result(self, mock_run_agent, mock_validator, tmp_path):
        """AST validation exception → score=0 for pattern, error logged, no crash."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.side_effect = Exception("AST parser crashed")
        mock_validator.validate_naming.return_value = _make_naming_result()

        test = AgentTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=1)

        assert result.pattern_score == 0.0
        assert len(result.errors) > 0

    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_naming_exception_produces_degraded_result(self, mock_run_agent, mock_validator, tmp_path):
        """Naming validation exception → score=0 for naming, error logged, no crash."""
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.side_effect = Exception("naming crashed")

        test = AgentTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=1)

        assert result.naming_score == 0.0
        assert len(result.errors) > 0

    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_tool_call_log_in_result(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        log = [{"step": 1, "tool": "read_file", "args": {}, "result_summary": "content"}]
        mock_run_agent.return_value = _make_agent_result(tool_call_log=log)
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        test = AgentTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=1)

        assert result.tool_call_log == log

    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_run_number_in_result(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        test = AgentTest(model="test-model", fixture_path=fixture_path)
        result = test.run(run_number=2)

        assert result.run_number == 2

    @patch("src.agent.ts_bugfix.test_runner.validator")
    @patch("src.agent.ts_bugfix.test_runner.run_agent")
    def test_passes_model_and_prompt_to_run_agent(self, mock_run_agent, mock_validator, tmp_path):
        fixture_path = _make_fixture(tmp_path)
        mock_run_agent.return_value = _make_agent_result()
        mock_validator.validate_compilation.return_value = _make_compilation_result()
        mock_validator.validate_ast_structure.return_value = _make_ast_result()
        mock_validator.validate_naming.return_value = _make_naming_result()

        test = AgentTest(model="qwen2.5-coder:7b", fixture_path=fixture_path)
        test.run(run_number=1)

        call_kwargs = mock_run_agent.call_args
        assert call_kwargs.kwargs.get("model") == "qwen2.5-coder:7b" or call_kwargs[1].get("model") == "qwen2.5-coder:7b" or call_kwargs[0][0] == "qwen2.5-coder:7b"
        task_arg = call_kwargs.kwargs.get("task") or (call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None)
        assert task_arg is not None
        assert "Fix TypeScript errors" in task_arg
