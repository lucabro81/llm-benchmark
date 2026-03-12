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

from src.agent.common.agent_client import (
    AgentRunResult,
    _make_observations_prune_callback,
    _make_step_data_callback,
    run_agent,
)


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
            steps=2,
            final_output="Done",
            tool_call_log=[],
            duration_sec=3.5,
            tokens_per_sec=45.0,
            errors=[],
        )
        assert result.succeeded is True
        assert result.steps == 2
        assert result.duration_sec == 3.5

    def test_errors_defaults_to_empty_list(self):
        result = AgentRunResult(
            succeeded=True,
            steps=1,
            final_output="",
            tool_call_log=[],
            duration_sec=1.0,
            tokens_per_sec=0.0,
        )
        assert result.errors == []

    def test_run_crashed_defaults_to_false(self):
        result = AgentRunResult(
            succeeded=True,
            steps=1,
            final_output="Done",
            tool_call_log=[],
            duration_sec=1.0,
            tokens_per_sec=0.0,
        )
        assert result.run_crashed is False


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

        result = run_agent(model="test-model", task="Fix it", tools=[], max_steps=5)

        assert isinstance(result, AgentRunResult)

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_succeeded_true_when_state_is_success(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_steps=5)

        assert result.succeeded is True

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_succeeded_false_when_state_is_max_steps_error(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("max_steps_error")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_steps=5)

        assert result.succeeded is False

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_succeeded_false_on_unexpected_exception(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.side_effect = RuntimeError("connection refused")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_steps=5)

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

        result = run_agent(model="m", task="t", tools=[], max_steps=5)

        assert len(result.tool_call_log) == 2
        assert result.tool_call_log[0]["tool"] == "read_file"
        assert result.tool_call_log[0]["step"] == 1
        assert result.tool_call_log[1]["tool"] == "write_file"
        assert result.tool_call_log[1]["step"] == 2

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_steps_equals_number_of_tool_calling_turns(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = [
            _make_action_step("read_file", {}, "content"),
            _make_action_step("run_compilation", {}, "Compilation succeeded."),
        ]
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_steps=5)

        assert result.steps == 2

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_duration_sec_is_positive(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_steps=5)

        assert result.duration_sec > 0

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_tokens_per_sec_computed_from_token_usage(self, mock_model_cls, mock_agent_cls):
        """tokens_per_sec = output_tokens / duration_sec (non-zero when tokens available)."""
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success", output_tokens=300)
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        result = run_agent(model="m", task="t", tools=[], max_steps=5)

        assert result.tokens_per_sec >= 0.0

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_passes_max_steps_to_agent(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        run_agent(model="m", task="t", tools=[], max_steps=3)

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
        run_agent(model="m", task="t", tools=dummy_tools, max_steps=5)

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
        run_agent(model="m", task="t", tools=[], max_steps=5)

        _, model_kwargs = mock_model_cls.call_args
        assert "192.168.1.10:11434" in model_kwargs.get("api_base", "")

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_calls_run_with_return_full_result_true(self, mock_model_cls, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        run_agent(model="m", task="Fix it", tools=[], max_steps=5)

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

        result = run_agent(model="m", task="t", tools=[], max_steps=5)

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

        result = run_agent(model="m", task="t", tools=[], max_steps=5)

        assert isinstance(result, AgentRunResult)
        assert len(result.errors) > 0

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_step_callbacks_passed_to_agent(self, mock_model_cls, mock_agent_cls):
        """ToolCallingAgent must receive step_callbacks for history pruning."""
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = []
        mock_agent_cls.return_value = mock_agent

        run_agent(model="m", task="t", tools=[], max_steps=5)

        _, agent_kwargs = mock_agent_cls.call_args
        assert "step_callbacks" in agent_kwargs
        assert len(agent_kwargs["step_callbacks"]) > 0


# ---------------------------------------------------------------------------
# _make_observations_prune_callback
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# _make_step_data_callback
# ---------------------------------------------------------------------------

class TestStepDataCallback:
    def _make_agent(self, steps, messages=None):
        agent = MagicMock()
        agent.memory.steps = steps
        agent.write_memory_to_messages.return_value = messages or [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user message"},
        ]
        return agent

    def test_appends_one_entry_per_callback_call(self):
        step_data = []
        cb = _make_step_data_callback(step_data, run_start=0.0)
        cb(MagicMock(), agent=self._make_agent([]))
        cb(MagicMock(), agent=self._make_agent([]))
        assert len(step_data) == 2

    def test_entry_has_duration_sec(self):
        step_data = []
        cb = _make_step_data_callback(step_data, run_start=0.0)
        cb(MagicMock(), agent=self._make_agent([]))
        assert "duration_sec" in step_data[0]
        assert step_data[0]["duration_sec"] >= 0.0

    def test_entry_has_context_chars(self):
        step_data = []
        cb = _make_step_data_callback(step_data, run_start=0.0)
        agent = self._make_agent([], messages=[{"role": "user", "content": "hello"}])
        cb(MagicMock(), agent=agent)
        assert "context_chars" in step_data[0]
        assert step_data[0]["context_chars"] == 5  # len("hello")

    def test_no_crash_if_agent_is_none(self):
        step_data = []
        cb = _make_step_data_callback(step_data, run_start=0.0)
        cb(MagicMock(), agent=None)  # must not raise
        assert len(step_data) == 0

    def test_no_crash_if_write_memory_raises(self):
        step_data = []
        cb = _make_step_data_callback(step_data, run_start=0.0)
        agent = MagicMock()
        agent.write_memory_to_messages.side_effect = RuntimeError("boom")
        cb(MagicMock(), agent=agent)
        assert len(step_data) == 1
        assert step_data[0]["context_chars"] == 0


# ---------------------------------------------------------------------------
# AgentRunResult — new per-step fields in tool_call_log
# ---------------------------------------------------------------------------

class TestToolCallLogEnrichment:
    def _run_with_steps(self, steps, mock_agent_cls, mock_model_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = steps
        mock_agent.write_memory_to_messages.return_value = [{"role": "user", "content": "ctx"}]
        mock_agent_cls.return_value = mock_agent
        return run_agent(model="m", task="t", tools=[], max_steps=5)

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_write_file_compile_passed_is_none(
        self, mock_model_cls, mock_agent_cls
    ):
        """write_file is no longer in _COMPILE_TOOLS — compile_passed must be None."""
        step = _make_action_step("write_file", {"path": "x.vue"}, "File written.")
        result = self._run_with_steps([step], mock_agent_cls, mock_model_cls)
        assert result.tool_call_log[0]["compile_passed"] is None

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_tool_call_log_entry_has_compile_passed_false_for_compile_errors(
        self, mock_model_cls, mock_agent_cls
    ):
        step = _make_action_step("run_compilation", {}, "error TS2345: bad type")
        result = self._run_with_steps([step], mock_agent_cls, mock_model_cls)
        assert result.tool_call_log[0]["compile_passed"] is False

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_tool_call_log_entry_compile_passed_none_for_read_file(
        self, mock_model_cls, mock_agent_cls
    ):
        step = _make_action_step("read_file", {"path": "x.vue"}, "file contents")
        result = self._run_with_steps([step], mock_agent_cls, mock_model_cls)
        assert result.tool_call_log[0]["compile_passed"] is None

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_tool_call_log_entry_has_duration_sec(self, mock_model_cls, mock_agent_cls):
        step = _make_action_step("write_file", {}, "File written.\nCompilation succeeded.")
        result = self._run_with_steps([step], mock_agent_cls, mock_model_cls)
        assert "duration_sec" in result.tool_call_log[0]
        assert result.tool_call_log[0]["duration_sec"] >= 0.0

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_tool_call_log_entry_has_context_chars(self, mock_model_cls, mock_agent_cls):
        step = _make_action_step("write_file", {}, "File written.\nCompilation succeeded.")
        result = self._run_with_steps([step], mock_agent_cls, mock_model_cls)
        assert "context_chars" in result.tool_call_log[0]
        assert isinstance(result.tool_call_log[0]["context_chars"], int)


# ---------------------------------------------------------------------------
# AgentRunResult — new aggregate fields
# ---------------------------------------------------------------------------

class TestAgentRunResultAggregates:
    def _run(self, steps, mock_agent_cls, mock_model_cls, run_result=None):
        mock_agent = MagicMock()
        mock_agent.run.return_value = run_result or _make_run_result("success", output_tokens=100, input_tokens=400)
        mock_agent.memory.steps = steps
        mock_agent.write_memory_to_messages.return_value = [{"role": "user", "content": "x"}]
        mock_agent_cls.return_value = mock_agent
        return run_agent(model="m", task="t", tools=[], max_steps=5)

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_total_input_tokens(self, mock_model_cls, mock_agent_cls):
        result = self._run([], mock_agent_cls, mock_model_cls, _make_run_result("success", input_tokens=400))
        assert result.total_input_tokens == 400

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_total_output_tokens(self, mock_model_cls, mock_agent_cls):
        result = self._run([], mock_agent_cls, mock_model_cls, _make_run_result("success", output_tokens=150))
        assert result.total_output_tokens == 150

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_first_compile_success_step_none_when_no_compile(self, mock_model_cls, mock_agent_cls):
        result = self._run([], mock_agent_cls, mock_model_cls)
        assert result.first_compile_success_step is None

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_first_compile_success_step_set_on_first_success(self, mock_model_cls, mock_agent_cls):
        """Only run_compilation calls determine compile_passed (write_file no longer in _COMPILE_TOOLS)."""
        steps = [
            _make_action_step("run_compilation", {}, "error TS1"),
            _make_action_step("run_compilation", {}, "Compilation succeeded."),
        ]
        result = self._run(steps, mock_agent_cls, mock_model_cls)
        assert result.first_compile_success_step == 2

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_compile_error_recovery_count(self, mock_model_cls, mock_agent_cls):
        """Only run_compilation calls track compile pass/fail transitions."""
        steps = [
            _make_action_step("run_compilation", {}, "error TS1"),
            _make_action_step("run_compilation", {}, "Compilation succeeded."),
            _make_action_step("run_compilation", {}, "error TS2"),
            _make_action_step("run_compilation", {}, "Compilation succeeded."),
        ]
        result = self._run(steps, mock_agent_cls, mock_model_cls)
        assert result.compile_error_recovery_count == 2

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_rag_queries_count(self, mock_model_cls, mock_agent_cls):
        steps = [
            _make_action_step("query_rag", {"query": "how to use Form"}, "result text"),
            _make_action_step("write_file", {}, "File written.\nCompilation succeeded."),
        ]
        result = self._run(steps, mock_agent_cls, mock_model_cls)
        assert result.rag_queries_count == 1

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_read_file_count(self, mock_model_cls, mock_agent_cls):
        steps = [
            _make_action_step("read_file", {"path": "a.vue"}, "content"),
            _make_action_step("read_file", {"path": "b.vue"}, "content"),
        ]
        result = self._run(steps, mock_agent_cls, mock_model_cls)
        assert result.read_file_count == 2

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_list_files_count(self, mock_model_cls, mock_agent_cls):
        steps = [_make_action_step("list_files", {"directory": "."}, "file1\nfile2")]
        result = self._run(steps, mock_agent_cls, mock_model_cls)
        assert result.list_files_count == 1

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_counts_zero_when_tools_not_used(self, mock_model_cls, mock_agent_cls):
        steps = [_make_action_step("write_file", {}, "File written.\nCompilation succeeded.")]
        result = self._run(steps, mock_agent_cls, mock_model_cls)
        assert result.rag_queries_count == 0
        assert result.read_file_count == 0
        assert result.list_files_count == 0


# ---------------------------------------------------------------------------
# _make_observations_prune_callback
# ---------------------------------------------------------------------------

class TestObservationsPruneCallback:
    """Tests for _make_observations_prune_callback.

    This callback only manages run_compilation observations.
    write_file content pruning is handled by ContextPruningModel._prune_messages().
    """

    def _make_step(self, tool_name, arguments, observations):
        step = MagicMock()
        tc = MagicMock()
        tc.name = tool_name
        tc.arguments = arguments
        step.tool_calls = [tc]
        step.observations = observations
        return step

    def _make_agent(self, steps):
        agent = MagicMock()
        agent.memory.steps = steps
        return agent

    def test_last_run_compilation_observation_kept(self):
        step = self._make_step("run_compilation", {}, "error TS2345: important error")
        agent = self._make_agent([step])
        cb = _make_observations_prune_callback()
        cb(MagicMock(), agent=agent)
        assert step.observations == "error TS2345: important error"

    def test_old_run_compilation_observations_replaced(self):
        old = self._make_step("run_compilation", {}, "old error")
        last = self._make_step("run_compilation", {}, "latest error")
        agent = self._make_agent([old, last])
        cb = _make_observations_prune_callback()
        cb(MagicMock(), agent=agent)
        assert old.observations == "(see latest compilation result)"
        assert last.observations == "latest error"

    def test_write_file_observations_untouched(self):
        """write_file observations are NOT managed by this callback."""
        step = self._make_step("write_file", {"path": "Foo.vue"}, "big code here")
        agent = self._make_agent([step])
        cb = _make_observations_prune_callback()
        cb(MagicMock(), agent=agent)
        assert step.observations == "big code here"

    def test_steps_without_tool_calls_untouched(self):
        step = MagicMock()
        step.tool_calls = None
        step.observations = "some planning text"
        agent = self._make_agent([step])
        cb = _make_observations_prune_callback()
        cb(MagicMock(), agent=agent)
        assert step.observations == "some planning text"

    def test_no_crash_if_agent_is_none(self):
        cb = _make_observations_prune_callback()
        cb(MagicMock(), agent=None)  # must not raise

    def test_no_crash_on_task_step_without_tool_calls_attr(self):
        """TaskStep objects don't have tool_calls attribute — must not raise AttributeError."""
        from unittest.mock import NonCallableMock
        task_step = NonCallableMock(spec=[])  # no attributes at all — simulates TaskStep
        agent = self._make_agent([task_step])
        cb = _make_observations_prune_callback()
        cb(MagicMock(), agent=agent)  # must not raise

    def test_other_tools_untouched(self):
        step = self._make_step("read_file", {"path": "foo.vue"}, "file contents here")
        agent = self._make_agent([step])
        cb = _make_observations_prune_callback()
        cb(MagicMock(), agent=agent)
        assert step.observations == "file contents here"


# ---------------------------------------------------------------------------
# run_crashed flag + final_answer tracking
# ---------------------------------------------------------------------------

class TestRunCrashedAndFinalAnswer:
    def _run_with_steps(self, steps, mock_agent_cls, mock_model_cls, side_effect=None):
        mock_agent = MagicMock()
        if side_effect is not None:
            mock_agent.run.side_effect = side_effect
        else:
            mock_agent.run.return_value = _make_run_result("success")
        mock_agent.memory.steps = steps
        mock_agent.write_memory_to_messages.return_value = [{"role": "user", "content": "ctx"}]
        mock_agent_cls.return_value = mock_agent
        return run_agent(model="m", task="t", tools=[], max_steps=5)

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_run_crashed_set_on_agent_exception(self, mock_model_cls, mock_agent_cls):
        """run_crashed must be True when agent.run() raises an exception."""
        result = self._run_with_steps(
            [], mock_agent_cls, mock_model_cls,
            side_effect=RuntimeError("Ollama 500 error")
        )
        assert result.run_crashed is True
        assert result.succeeded is False

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_run_crashed_false_on_success(self, mock_model_cls, mock_agent_cls):
        """run_crashed must be False on a normal successful run."""
        result = self._run_with_steps([], mock_agent_cls, mock_model_cls)
        assert result.run_crashed is False

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_final_answer_in_tool_call_log(self, mock_model_cls, mock_agent_cls):
        """final_answer tool call must appear in tool_call_log."""
        step = _make_action_step("final_answer", {"answer": "Done"}, "Done")
        result = self._run_with_steps([step], mock_agent_cls, mock_model_cls)
        tools_called = [e["tool"] for e in result.tool_call_log]
        assert "final_answer" in tools_called

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_final_answer_not_counted_in_step_count(self, mock_model_cls, mock_agent_cls):
        """A step with ONLY final_answer must NOT increment step_count."""
        step = _make_action_step("final_answer", {"answer": "Done"}, "Done")
        result = self._run_with_steps([step], mock_agent_cls, mock_model_cls)
        assert result.steps == 0

    @patch("src.agent.common.agent_client.ToolCallingAgent")
    @patch("src.agent.common.agent_client.OpenAIServerModel")
    def test_final_answer_after_real_tool_still_one_step(self, mock_model_cls, mock_agent_cls):
        """A step with write_file + final_answer counts as 1 step (not 0, not 2)."""
        step = MagicMock()
        step.tool_calls = [
            _make_tool_call("write_file", {"path": "x.vue", "content": "code"}),
            _make_tool_call("final_answer", {"answer": "Done"}),
        ]
        step.observations = "File written."
        result = self._run_with_steps([step], mock_agent_cls, mock_model_cls)
        assert result.steps == 1
        tools_logged = [e["tool"] for e in result.tool_call_log]
        assert "write_file" in tools_logged
        assert "final_answer" in tools_logged
