"""smolagents wrapper for agent benchmark runs.

Provides run_agent() which:
- Creates OpenAIServerModel pointing at Ollama's /v1 endpoint
- Runs a ToolCallingAgent with the provided tools
- Collects step logs from agent.memory.steps for inspectability
- Returns AgentRunResult with metrics and tool call history

smolagents API (verified against source):
- agent.run(task, return_full_result=True) → RunResult
- RunResult.state: "success" | "max_steps_error"
- RunResult.token_usage: TokenUsage(input_tokens, output_tokens)
- agent.memory.steps: List[ActionStep]
- ActionStep.tool_calls: List[ToolCall(name, arguments, id)]
- ActionStep.observations: str (concatenated tool results)
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from smolagents import ToolCallingAgent
from smolagents.models import OpenAIServerModel

from src.common.ollama_client import get_ollama_base_url

# Tools whose observations indicate compilation outcome.
_COMPILE_TOOLS = {"write_file", "run_compilation"}


@dataclass
class AgentRunResult:
    """Result of a single agent execution loop.

    Attributes:
        succeeded: True if agent finished before max_iterations (state == "success").
        steps: Number of agent steps taken (write_file + run_compilation calls).
        final_output: Agent's final answer string, or empty string on failure.
        tool_call_log: Per-step entries with tool, args, result_summary, compile_passed,
            duration_sec, context_chars.
        duration_sec: Wall-clock time for the full agent loop.
        tokens_per_sec: output_tokens / duration_sec (0.0 if unavailable).
        errors: Any internal errors captured during the run.
        total_input_tokens: Total input tokens across all LLM calls.
        total_output_tokens: Total output tokens across all LLM calls.
        first_compile_success_step: Step number of the first successful compilation,
            or None if compilation never succeeded.
        compile_error_recovery_count: Number of times compilation went from
            failure to success across consecutive compile steps.
        rag_queries_count: Number of query_rag tool calls (0 for non-RAG tests).
        read_file_count: Number of read_file tool calls (0 for non-full tests).
        list_files_count: Number of list_files tool calls (0 for non-full tests).
    """
    succeeded: bool
    steps: int
    final_output: str
    tool_call_log: List[Dict[str, Any]]
    duration_sec: float
    tokens_per_sec: float
    errors: List[str] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    first_compile_success_step: Optional[int] = None
    compile_error_recovery_count: int = 0
    rag_queries_count: int = 0
    read_file_count: int = 0
    list_files_count: int = 0


def _make_observations_prune_callback():
    """Return a step_callback that prunes stale run_compilation observations.

    Fires after each step via ToolCallingAgent step_callbacks — the official
    hook for post-step memory management — and mutates only ActionStep.observations,
    which is a plain public dataclass field designed to be updated.

    Pruning rule:
    - run_compilation: only the most recent step's observations are kept; older
      ones become "(see latest compilation result)" so the model is not confused
      by superseded errors.
    - All other tools are left untouched.

    Note on context growth: the assistant message (raw LLM output containing the
    written file) grows linearly per step. For the tasks in this benchmark
    (max_steps 10–30, models with 32k–128k context), this is acceptable and the
    tests pass reliably.
    """
    def _prune(memory_step, agent=None):
        if agent is None:
            return
        steps = agent.memory.steps

        last_compile_idx = None
        for i, step in enumerate(steps):
            tool_calls = getattr(step, "tool_calls", None) or []
            if any(tc.name == "run_compilation" for tc in tool_calls):
                last_compile_idx = i

        for i, step in enumerate(steps):
            tool_calls = getattr(step, "tool_calls", None) or []
            if not tool_calls:
                continue
            for tc in tool_calls:
                if tc.name == "run_compilation" and i != last_compile_idx:
                    step.observations = "(see latest compilation result)"

    return _prune


def _make_step_data_callback(step_data: List[Dict[str, Any]], run_start: float):
    """Return a step_callback that captures per-step timing and context size.

    Appends one entry per step to step_data:
        {"duration_sec": float, "context_chars": int}

    duration_sec is the wall-clock time elapsed since the previous step
    (or since run_start for the first step).

    context_chars is the total character count of all messages that smolagents
    would send to the model at the next step (after pruning).

    Args:
        step_data: Shared list to append entries to.
        run_start: time.time() value recorded at the start of the agent run.
    """
    last_time = [run_start]

    def _capture(memory_step, agent=None):
        if agent is None:
            return
        now = time.time()
        duration = round(now - last_time[0], 3)
        last_time[0] = now

        context_chars = 0
        try:
            messages = agent.write_memory_to_messages()
            for m in messages:
                if isinstance(m, dict):
                    content = m.get("content", "")
                else:
                    content = getattr(m, "content", "")
                context_chars += len(str(content))
        except Exception:
            pass

        step_data.append({"duration_sec": duration, "context_chars": context_chars})

    return _capture


def _make_prompt_logger_callback(log_path: Path):
    """Return a step_callback that logs the message list as smolagents builds it.

    Writes a JSONL file where each line is:
      {"step": N, "messages": [...], "n_messages": M, "approx_chars": K}

    Calls agent.write_memory_to_messages() directly — no filtering applied —
    so the log reflects exactly what smolagents passes to the model at the
    next step (after observations pruning by _make_observations_prune_callback).
    """
    step_counter = [0]
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def _log(memory_step, agent=None):
        if agent is None:
            return
        step_counter[0] += 1
        try:
            messages = agent.write_memory_to_messages()
            serializable = [
                {"role": m.get("role", ""), "content": m.get("content", "")}
                if isinstance(m, dict)
                else {"role": getattr(m, "role", ""), "content": str(getattr(m, "content", ""))}
                for m in messages
            ]
            total_chars = sum(len(str(m.get("content", ""))) for m in serializable)
            entry = {
                "step": step_counter[0],
                "n_messages": len(serializable),
                "approx_chars": total_chars,
                "messages": serializable,
            }
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"step": step_counter[0], "error": str(exc)}) + "\n")

    return _log


def _compile_passed_from_observations(tool_name: str, observations: str) -> Optional[bool]:
    """Derive compile_passed from a tool's observation string.

    Returns True/False for compile tools, None for all others.
    """
    if tool_name not in _COMPILE_TOOLS:
        return None
    return "Compilation succeeded." in observations and "Compilation errors:" not in observations


def run_agent(
    model: str,
    task: str,
    tools: List,
    max_steps: int = 5,
    extra_system_prompt: str = "",
    prompt_log_path: Optional[Path] = None,
) -> AgentRunResult:
    """Execute the agent loop and return a structured result.

    Args:
        model: Ollama model name (e.g. 'qwen2.5-coder:7b-instruct-q8_0').
        task: Task description string to run as the agent's goal.
        tools: List of @tool-decorated callables (from make_tools()).
        max_steps: Maximum number of agent steps before forced stop.
        extra_system_prompt: Appended to the smolagents system prompt.
        prompt_log_path: If set, write per-step message logs to this JSONL file.

    Returns:
        AgentRunResult with step log, success flag, timing, and token metrics.
    """
    base_url = get_ollama_base_url()

    llm = OpenAIServerModel(
        model_id=model,
        api_base=f"{base_url}/v1",
        api_key="ollama",
    )

    start_time = time.time()
    step_data: List[Dict[str, Any]] = []

    step_callbacks = [
        _make_observations_prune_callback(),
        _make_step_data_callback(step_data, run_start=start_time),
    ]
    if prompt_log_path is not None:
        step_callbacks.append(_make_prompt_logger_callback(prompt_log_path))

    agent = ToolCallingAgent(
        tools=tools,
        model=llm,
        max_steps=max_steps,
        step_callbacks=step_callbacks,
    )

    # Inject JSON format rules into the system prompt so they appear in every API call.
    # Small models (e.g. qwen2.5-coder:7b) tend to prepend reasoning text before the JSON
    # block, which causes smolagents to fail parsing. Injecting this rule here (rather than
    # in the task prompt) ensures it is present as the SYSTEM message at every step.
    _FORMAT_REMINDER = (
        "\n\n## CRITICAL FORMAT RULE\n"
        "When calling a tool, output ONLY a valid JSON code block — no explanation, "
        "no reasoning, no text before or after it.\n"
        "```json\n"
        '{"name": "tool_name", "arguments": {"param": "value"}}\n'
        "```\n"
        "JSON string rules:\n"
        "- Newlines inside strings MUST be \\n (backslash + n), NOT literal line breaks\n"
        '- Double quotes inside strings MUST be escaped as \\"\n'
        "If you add any text outside the JSON block, the tool call will fail."
    )
    try:
        agent.memory.system_prompt.system_prompt += _FORMAT_REMINDER
        if extra_system_prompt:
            agent.memory.system_prompt.system_prompt += extra_system_prompt
    except Exception:
        pass  # defensive: skip injection if memory is unavailable

    tool_call_log: List[Dict[str, Any]] = []
    errors: List[str] = []
    succeeded = False
    final_output = ""
    total_output_tokens = 0
    total_input_tokens = 0
    run_result = None

    try:
        run_result = agent.run(task, return_full_result=True)
        succeeded = run_result.state == "success"
        final_output = str(run_result.output) if run_result.output else ""
        try:
            total_output_tokens = run_result.token_usage.output_tokens or 0
            total_input_tokens = run_result.token_usage.input_tokens or 0
        except Exception:
            pass
    except Exception as e:
        errors.append(f"Agent run error: {e}")
        succeeded = False
    finally:
        duration_sec = time.time() - start_time

    tokens_per_sec = (
        total_output_tokens / duration_sec
        if duration_sec > 0 and total_output_tokens > 0
        else 0.0
    )

    step_count = 0
    try:
        for i, step in enumerate(agent.memory.steps):
            tool_calls = getattr(step, "tool_calls", None) or []
            # Exclude planning steps (no tool_calls) and the final_answer step
            real_calls = [tc for tc in tool_calls if getattr(tc, "name", "") != "final_answer"]
            if not real_calls:
                continue
            step_count += 1

            observations = getattr(step, "observations", "") or ""
            obs_str = str(observations)
            result_summary = obs_str[:200] + "..." if len(obs_str) > 200 else obs_str

            # Per-step timing and context from step_data (index matches real step order).
            # step_data is indexed by callback invocation order, not by step_count,
            # because TaskStep (planning) steps also trigger the callback.
            # We use i (raw index into memory.steps) to align with step_data entries.
            sd = step_data[i] if i < len(step_data) else {}
            step_duration = sd.get("duration_sec", 0.0)
            context_chars = sd.get("context_chars", 0)

            for tc in real_calls:
                tool_name = getattr(tc, "name", "unknown")
                compile_passed = _compile_passed_from_observations(tool_name, obs_str)
                tool_call_log.append({
                    "step": step_count,
                    "tool": tool_name,
                    "args": getattr(tc, "arguments", {}),
                    "result_summary": result_summary,
                    "compile_passed": compile_passed,
                    "duration_sec": step_duration,
                    "context_chars": context_chars,
                })
    except Exception as e:
        errors.append(f"Log extraction error: {e}")

    # Derive aggregate metrics from tool_call_log.
    first_compile_success_step: Optional[int] = None
    compile_error_recovery_count = 0
    prev_compile_passed: Optional[bool] = None

    for entry in tool_call_log:
        cp = entry.get("compile_passed")
        if cp is not None:
            if cp and first_compile_success_step is None:
                first_compile_success_step = entry["step"]
            if cp and prev_compile_passed is False:
                compile_error_recovery_count += 1
            prev_compile_passed = cp

    rag_queries_count = sum(1 for e in tool_call_log if e.get("tool") == "query_rag")
    read_file_count = sum(1 for e in tool_call_log if e.get("tool") == "read_file")
    list_files_count = sum(1 for e in tool_call_log if e.get("tool") == "list_files")

    return AgentRunResult(
        succeeded=succeeded,
        steps=step_count,
        final_output=final_output,
        tool_call_log=tool_call_log,
        duration_sec=duration_sec,
        tokens_per_sec=tokens_per_sec,
        errors=errors,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        first_compile_success_step=first_compile_success_step,
        compile_error_recovery_count=compile_error_recovery_count,
        rag_queries_count=rag_queries_count,
        read_file_count=read_file_count,
        list_files_count=list_files_count,
    )
