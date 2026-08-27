"""Secret-aware terminal tracing for LocalCoder agent events."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
import shlex
import sys
from typing import Any, TextIO

from tools.base import ToolResult, truncate_text

_STAGES = {
    "write_file": "EDIT",
    "replace_text": "EDIT",
    "run_command": "VERIFY",
    "finish": "DONE",
}
_GENERIC_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{12,}\b"),
    re.compile(
        r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*"
        r"(['\"]?)[^\s,'\"]+\2"
    ),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
)


class TraceLogger:
    """Print concise loop events without exposing tool payloads or secrets."""

    def __init__(
        self,
        stream: TextIO | None = None,
        secrets: Iterable[str] = (),
    ) -> None:
        self._stream = sys.stdout if stream is None else stream
        self._secrets = tuple(
            secret for secret in secrets if isinstance(secret, str) and secret
        )

    def log_tool(
        self,
        step: int,
        tool_name: str,
        arguments: Mapping[str, Any] | None,
        result: ToolResult,
        changed_files: Iterable[str],
        verification_runs: list[dict[str, Any]],
        verification_current: bool,
    ) -> None:
        stage = _STAGES.get(tool_name, "EXPLORE")
        lines = [
            f"Step {step} · {stage}",
            f"Tool: {tool_name}",
            f"Arguments: {self._safe_arguments(tool_name, arguments)}",
            f"Status: {'SUCCESS' if result.success else 'FAILURE'}",
            f"Result: {self._safe_result(tool_name, result)}",
            f"Changed files: {self._changed_files(changed_files)}",
        ]
        if tool_name == "finish":
            lines.append(
                "Final verification: "
                + self._verification_status(verification_runs, verification_current)
            )
        print("\n".join(lines), file=self._stream)

    def log_terminal(
        self,
        step: int,
        message: str,
        changed_files: Iterable[str],
        verification_runs: list[dict[str, Any]],
        verification_current: bool,
    ) -> None:
        lines = [
            f"Step {step} · DONE",
            "Tool: (agent)",
            "Status: FAILURE",
            f"Result: {self._redact(message)}",
            f"Changed files: {self._changed_files(changed_files)}",
            "Final verification: "
            + self._verification_status(verification_runs, verification_current),
        ]
        print("\n".join(lines), file=self._stream)

    def _safe_arguments(
        self,
        tool_name: str,
        arguments: Mapping[str, Any] | None,
    ) -> str:
        if not arguments:
            return "(none)"
        items: list[str] = []
        path = arguments.get("path")
        if isinstance(path, str):
            items.append("path=" + self._redact(path))
        if tool_name == "run_command":
            items.append("command=" + self._command_name(arguments.get("command")))
        elif tool_name == "search_text":
            query = arguments.get("query")
            items.append(f"query_chars={len(query) if isinstance(query, str) else 0}")
        elif tool_name == "write_file":
            content = arguments.get("content")
            items.append(
                f"content_chars={len(content) if isinstance(content, str) else 0}"
            )
        elif tool_name == "replace_text":
            for name in ("old_text", "new_text"):
                value = arguments.get(name)
                items.append(
                    f"{name}_chars={len(value) if isinstance(value, str) else 0}"
                )
        elif tool_name == "finish":
            for name in ("summary", "verification", "limitations"):
                value = arguments.get(name)
                if value is not None:
                    items.append(
                        f"{name}_chars={len(value) if isinstance(value, str) else 0}"
                    )
        return ", ".join(items) if items else "(omitted)"

    def _safe_result(self, tool_name: str, result: ToolResult) -> str:
        if tool_name == "run_command":
            return (
                f"exit_code={result.metadata.get('exit_code')}, "
                f"timed_out={result.metadata.get('timed_out', False)}, "
                f"output_chars={len(result.output)}, "
                "output_truncated="
                f"{result.metadata.get('output_truncated', False)}"
            )
        value = result.error if result.error else result.output
        concise, _ = truncate_text(value or "(no output)", 500)
        return self._redact(" ".join(concise.splitlines()))

    def _command_name(self, command: object) -> str:
        if not isinstance(command, str) or not command.strip():
            return "(invalid)"
        try:
            tokens = shlex.split(command, posix=False)
        except ValueError:
            tokens = command.split()
        if not tokens:
            return "(invalid)"
        return self._redact(tokens[0].strip("'\""))

    def _redact(self, text: str) -> str:
        redacted = text
        for secret in self._secrets:
            redacted = redacted.replace(secret, "[REDACTED]")
        for pattern in _GENERIC_SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted

    def _changed_files(self, changed_files: Iterable[str]) -> str:
        files = sorted(changed_files)
        return self._redact(", ".join(files)) if files else "(none)"

    @staticmethod
    def _verification_status(
        verification_runs: list[dict[str, Any]],
        verification_current: bool,
    ) -> str:
        if verification_runs and verification_runs[-1].get("success") is not True:
            return "FAILURE"
        if verification_runs and verification_current:
            return "SUCCESS"
        if verification_runs:
            return "STALE"
        return "NOT RUN"
