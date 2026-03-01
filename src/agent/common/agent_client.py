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

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

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
    iterations: int
    final_output: str
    tool_call_log: List[Dict[str, Any]]
    duration_sec: float
    tokens_per_sec: float
    errors: List[str] = field(default_factory=list)


def run_agent(
    model: str,
    task: str,
    tools: List,
    max_iterations: int = 5,
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

    agent = ToolCallingAgent(
        tools=tools,
        model=llm,
        max_steps=max_iterations,
    )

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
        for step_idx, step in enumerate(agent.memory.steps):
            step_count += 1
            tool_calls = getattr(step, "tool_calls", None) or []
            observations = getattr(step, "observations", "") or ""
            result_summary = (
                str(observations)[:200] + "..."
                if len(str(observations)) > 200
                else str(observations)
            )
            for tc in tool_calls:
                tool_call_log.append({
                    "step": step_idx + 1,
                    "tool": getattr(tc, "name", "unknown"),
                    "args": getattr(tc, "arguments", {}),
                    "result_summary": result_summary,
                })
    except Exception as e:
        errors.append(f"Log extraction error: {e}")

    return AgentRunResult(
        succeeded=succeeded,
        iterations=step_count,
        final_output=final_output,
        tool_call_log=tool_call_log,
        duration_sec=duration_sec,
        tokens_per_sec=tokens_per_sec,
        errors=errors,
    )
