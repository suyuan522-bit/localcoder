"""Autonomous single-agent loop primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from config import MAX_STEPS
from llm_client import LLMClientError, LLMResponse, ToolCall
from prompts import SYSTEM_PROMPT
from tools.base import ToolResult
from tools.registry import ToolRegistry


@dataclass(slots=True)
class AgentState:
    """Small explicit state owned by one LocalCoder task run."""

    task: str
    step_count: int = 0
    modified_files: set[str] = field(default_factory=set)
    verification_runs: list[dict[str, Any]] = field(default_factory=list)
    last_error: str | None = None
    last_edit_step: int | None = None
    finished: bool = False
    final_summary: str | None = None
    final_verification: str | None = None
    final_limitations: str | None = None


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    """Controlled outcome returned by one agent run."""

    success: bool
    message: str


class AgentCore:
    """Coordinate model calls, tool dispatch, observations, and termination."""

    def __init__(
        self,
        llm_client: Any,
        registry: ToolRegistry,
        task: str,
        max_steps: int = MAX_STEPS,
    ) -> None:
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")
        if (
            isinstance(max_steps, bool)
            or not isinstance(max_steps, int)
            or max_steps <= 0
        ):
            raise ValueError("max_steps must be a positive integer")

        self._llm_client = llm_client
        self._registry = registry
        self._max_steps = max_steps
        self.state = AgentState(task=task)
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]
        self._register_finish_tool()

    def run(self) -> AgentRunResult:
        """Run until explicit finish, controlled failure, or MAX_STEPS."""

        try:
            return self._run_loop()
        except KeyboardInterrupt:
            message = "Agent interrupted by user."
            self.state.last_error = message
            return AgentRunResult(success=False, message=message)

    def _run_loop(self) -> AgentRunResult:
        for step in range(1, self._max_steps + 1):
            self.state.step_count = step
            try:
                response = self._llm_client.complete(
                    self.messages,
                    self._registry.definitions(),
                )
            except LLMClientError as exc:
                message = str(exc)
                self.state.last_error = message
                return AgentRunResult(success=False, message=message)

            self.messages.append(_assistant_message(response))
            for call in response.tool_calls:
                if call.name == "finish" and len(response.tool_calls) > 1:
                    result = ToolResult(
                        success=False,
                        error=(
                            "finish must be the only tool call in an "
                            "assistant response"
                        ),
                        metadata={
                            "tool": "finish",
                            "error_type": "invalid_finish_batch",
                        },
                    )
                else:
                    result = self._dispatch(call)
                self.messages.append(_tool_observation(call.id, result))
                if not result.success:
                    self.state.last_error = result.error
                if self.state.finished:
                    return AgentRunResult(
                        success=True,
                        message=self._final_message(),
                    )

        message = f"Agent stopped after reaching MAX_STEPS ({self._max_steps})."
        self.state.last_error = message
        return AgentRunResult(success=False, message=message)

    def _dispatch(self, call: ToolCall) -> ToolResult:
        if call.arguments is None:
            return ToolResult(
                success=False,
                error=call.argument_error or "Tool arguments are invalid.",
                metadata={
                    "tool": call.name,
                    "error_type": "invalid_tool_arguments",
                },
            )
        return self._registry.dispatch(call.name, call.arguments)

    def _register_finish_tool(self) -> None:
        self._registry.register(
            "finish",
            "Finish the task explicitly with a summary and verification evidence.",
            {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "verification": {"type": "string"},
                    "limitations": {"type": "string"},
                },
                "required": ["summary", "verification"],
                "additionalProperties": False,
            },
            self._finish,
        )

    def _finish(
        self,
        summary: str,
        verification: str,
        limitations: str | None = None,
    ) -> ToolResult:
        if not isinstance(summary, str) or not summary.strip():
            return ToolResult(
                success=False,
                error="summary must be a non-empty string",
                metadata={"tool": "finish", "error_type": "invalid_arguments"},
            )
        if not isinstance(verification, str) or not verification.strip():
            return ToolResult(
                success=False,
                error="verification must be a non-empty string",
                metadata={"tool": "finish", "error_type": "invalid_arguments"},
            )
        if limitations is not None and not isinstance(limitations, str):
            return ToolResult(
                success=False,
                error="limitations must be a string or null",
                metadata={"tool": "finish", "error_type": "invalid_arguments"},
            )

        self.state.final_summary = summary.strip()
        self.state.final_verification = verification.strip()
        self.state.final_limitations = (
            limitations.strip() if limitations and limitations.strip() else None
        )
        self.state.finished = True
        return ToolResult(
            success=True,
            output="Task finished.",
            metadata={"tool": "finish", "finished": True},
        )

    def _final_message(self) -> str:
        changed_files = (
            ", ".join(sorted(self.state.modified_files))
            if self.state.modified_files
            else "(none)"
        )
        lines = [
            f"Summary: {self.state.final_summary}",
            f"Changed files: {changed_files}",
            f"Verification: {self.state.final_verification}",
        ]
        if self.state.final_limitations:
            lines.append(f"Limitations: {self.state.final_limitations}")
        return "\n".join(lines)


def _assistant_message(response: LLMResponse) -> dict[str, Any]:
    message: dict[str, Any] = {
        "role": "assistant",
        "content": response.text,
    }
    if response.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(
                        call.arguments if call.arguments is not None else {},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            }
            for call in response.tool_calls
        ]
    return message


def _tool_observation(call_id: str, result: ToolResult) -> dict[str, Any]:
    content = json.dumps(
        {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "metadata": result.metadata,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": content,
    }
