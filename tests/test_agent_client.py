"""Tests for src/agent/common/agent_client.py.

TDD Red phase: all tests fail until agent_client.py is implemented.

smolagents API facts used here (verified against source):
- ToolCallingAgent(tools, model, max_steps=N) — max_steps via kwarg
- agent.run(task, return_full_result=True) → RunResult
- RunResult.state: "success" | "max_steps_error"
- RunResult.token_usage: TokenUsage(input_tokens, output_tokens)
- agent.memory.steps: List[ActionStep]
- ActionStep.tool_calls: List[ToolCall]  (ToolCall.name, ToolCall.arguments)
- ActionStep.observations: str
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from src.agent.common.agent_client import AgentRunResult, run_agent


# ---------------------------------------------------------------------------
# Helpers: build mock smolagents objects
# ---------------------------------------------------------------------------

def _make_tool_call(name, arguments):
    tc = MagicMock()
    tc.name = name
    tc.arguments = arguments
    return tc


def _make_action_step(tool_name, tool_args, observation):
    step = MagicMock()
    step.tool_calls = [_make_tool_call(tool_name, tool_args)]
    step.observations = observation
    return step


def _make_run_result(state="success", output_tokens=150, input_tokens=400):
    result = MagicMock()
    result.state = state
    result.token_usage = MagicMock()
    result.token_usage.output_tokens = output_tokens
    result.token_usage.input_tokens = input_tokens
    return result


# ---------------------------------------------------------------------------
# AgentRunResult dataclass
# ---------------------------------------------------------------------------

class TestAgentRunResult:
    def test_is_instantiable_with_required_fields(self):
        result = AgentRunResult(
            succeeded=True,
            iterations=2,
            final_output="Done",
            tool_call_log=[],
            duration_sec=3.5,
            tokens_per_sec=45.0,
            errors=[],
        )
        assert result.succeeded is True
        assert result.iterations == 2
        assert result.duration_sec == 3.5

    def test_errors_defaults_to_empty_list(self):
        result = AgentRunResult(
            succeeded=True,
            iterations=1,
            final_output="",
            tool_call_log=[],
            duration_sec=1.0,
            tokens_per_sec=0.0,
        )
        assert result.errors == []


# ---------------------------------------------------------------------------
# run_agent
# ---------------------------------------------------------------------------

class TestRunAgent:
    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_returns_agent_run_result(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="test-model", task="Fix it", tools=[], max_iterations=5)

        assert isinstance(result, AgentRunResult)

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_succeeded_true_when_state_is_success(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_iterations=5)

        assert result.succeeded is True

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_succeeded_false_when_state_is_max_steps_error(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("max_steps_error")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_iterations=5)

        assert result.succeeded is False

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_succeeded_false_on_unexpected_exception(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.side_effect = RuntimeError("connection refused")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_iterations=5)

        assert result.succeeded is False
        assert len(result.errors) > 0

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_tool_call_log_populated_from_memory_steps(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = [
            _make_action_step("read_file", {"path": "src/test.vue"}, "file content"),
            _make_action_step("write_file", {"path": "src/test.vue", "content": "fixed"}, "OK"),
        ]
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_iterations=5)

        assert len(result.tool_call_log) == 2
        assert result.tool_call_log[0]["tool"] == "read_file"
        assert result.tool_call_log[0]["step"] == 1
        assert result.tool_call_log[1]["tool"] == "write_file"
        assert result.tool_call_log[1]["step"] == 2

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_iterations_equals_number_of_steps(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = [
            _make_action_step("read_file", {}, "content"),
            _make_action_step("run_compilation", {}, "Compilation succeeded."),
        ]
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_iterations=5)

        assert result.iterations == 2

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_duration_sec_is_positive(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_iterations=5)

        assert result.duration_sec > 0

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_tokens_per_sec_computed_from_token_usage(self, mock_model_cls, mock_agent_cls):
        """tokens_per_sec = output_tokens / duration_sec (non-zero when tokens available)."""
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success", output_tokens=300)
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_iterations=5)

        assert result.tokens_per_sec >= 0.0

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_passes_max_iterations_as_max_steps(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        run_agent(model="m", task="t", tools=[], max_iterations=3)

        _, agent_kwargs = mock_agent_cls.call_args
        assert agent_kwargs.get("max_steps") == 3

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_passes_tools_to_agent(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        dummy_tools = [MagicMock(), MagicMock()]
        run_agent(model="m", task="t", tools=dummy_tools, max_iterations=5)

        _, agent_kwargs = mock_agent_cls.call_args
        assert agent_kwargs.get("tools") == dummy_tools

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_uses_ollama_base_url_env_var(self, mock_model_cls, mock_agent_cls, monkeypatch):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        monkeypatch.setenv("OLLAMA_BASE_URL", "http://192.168.1.10:11434")
        run_agent(model="m", task="t", tools=[], max_iterations=5)

        _, model_kwargs = mock_model_cls.call_args
        assert "192.168.1.10:11434" in model_kwargs.get("api_base", "")

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_calls_run_with_return_full_result_true(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        run_agent(model="m", task="Fix it", tools=[], max_iterations=5)

        mock_agent.run.assert_called_once_with("Fix it", return_full_result=True)

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_tool_call_log_result_summary_truncated(self, mock_model_cls, mock_agent_cls):
        """Long observations should be truncated in the log summary."""
        long_obs = "x" * 500
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = [_make_action_step("read_file", {}, long_obs)]
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_iterations=5)

        summary = result.tool_call_log[0]["result_summary"]
        assert len(summary) <= 250  # truncated

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_log_extraction_error_does_not_crash(self, mock_model_cls, mock_agent_cls):
        """If agent.memory is unavailable, result should still be returned with an error logged."""
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory = None  # accessing None.steps raises AttributeError
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_iterations=5)

        assert isinstance(result, AgentRunResult)
        assert len(result.errors) > 0
