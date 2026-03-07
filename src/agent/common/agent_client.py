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


@dataclass
class AgentRunResult:
    """Result of a single agent execution loop.

    Attributes:
        succeeded: True if agent finished before max_iterations (state == "success").
        iterations: Number of agent steps taken.
        final_output: Agent's final answer string, or empty string on failure.
        tool_call_log: [{step, tool, args, result_summary}] for inspectability.
        duration_sec: Wall-clock time for the full agent loop.
        tokens_per_sec: output_tokens / duration_sec (0.0 if unavailable).
        errors: Any internal errors captured during the run.
    """
    succeeded: bool
    steps: int
    final_output: str
    tool_call_log: List[Dict[str, Any]]
    duration_sec: float
    tokens_per_sec: float
    errors: List[str] = field(default_factory=list)


def _make_prune_callback():
    """Return a step_callback that prunes old tool observations from agent history.

    Fires after each step (via ToolCallingAgent step_callbacks) and mutates
    agent.memory.steps in-place so that write_memory_to_messages() at the next
    step sees a leaner context:

    - write_file: observations replaced with "Wrote file <path>." — removes the
      full file code from the context, keeping only the intent.
    - run_compilation: only the most recent step's observations are kept; older
      ones are replaced with "(see latest compilation result)" — the model only
      needs the latest error to iterate.
    - All other tools (read_file, list_files, query_rag) are left untouched.
    """
    def _prune(memory_step, agent=None):
        if agent is None:
            return
        steps = agent.memory.steps

        # Find index of the most recent run_compilation step
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
                if tc.name == "write_file":
                    path = tc.arguments.get("path", "unknown") if isinstance(tc.arguments, dict) else "unknown"
                    step.observations = f"Wrote file {path}."
                elif tc.name == "run_compilation" and i != last_compile_idx:
                    step.observations = "(see latest compilation result)"

    return _prune


def _make_prompt_logger_callback(log_path: Path):
    """Return a step_callback that logs the full message list sent to the model at each step.

    Writes a JSONL file where each line is:
      {"step": N, "messages": [...], "n_messages": M, "approx_chars": K}

    Uses agent.memory.write_memory_to_messages() — the same call smolagents makes
    internally before each API request — so the log reflects exactly what the model sees.
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
        max_iterations: Maximum number of agent steps before forced stop.

    Returns:
        AgentRunResult with step log, success flag, timing, and token metrics.
    """
    base_url = get_ollama_base_url()

    llm = OpenAIServerModel(
        model_id=model,
        api_base=f"{base_url}/v1",
        api_key="ollama",
    )

    step_callbacks = [_make_prune_callback()]
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
    output_tokens = 0
    start_time = time.time()

    try:
        run_result = agent.run(task, return_full_result=True)
        succeeded = run_result.state == "success"
        final_output = str(run_result.output) if run_result.output else ""
        try:
            output_tokens = run_result.token_usage.output_tokens or 0
        except Exception:
            output_tokens = 0
    except Exception as e:
        errors.append(f"Agent run error: {e}")
        succeeded = False
    finally:
        duration_sec = time.time() - start_time

    tokens_per_sec = output_tokens / duration_sec if duration_sec > 0 and output_tokens > 0 else 0.0

    step_count = 0
    try:
        for step in agent.memory.steps:
            tool_calls = getattr(step, "tool_calls", None) or []
            # Exclude planning steps (no tool_calls) and the final_answer step
            real_calls = [tc for tc in tool_calls if getattr(tc, "name", "") != "final_answer"]
            if not real_calls:
                continue
            step_count += 1
            observations = getattr(step, "observations", "") or ""
            result_summary = (
                str(observations)[:200] + "..."
                if len(str(observations)) > 200
                else str(observations)
            )
            for tc in real_calls:
                tool_call_log.append({
                    "step": step_count,
                    "tool": getattr(tc, "name", "unknown"),
                    "args": getattr(tc, "arguments", {}),
                    "result_summary": result_summary,
                })
    except Exception as e:
        errors.append(f"Log extraction error: {e}")

    return AgentRunResult(
        succeeded=succeeded,
        steps=step_count,
        final_output=final_output,
        tool_call_log=tool_call_log,
        duration_sec=duration_sec,
        tokens_per_sec=tokens_per_sec,
        errors=errors,
    )
