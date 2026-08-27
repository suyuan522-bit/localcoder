"""Bounded conversation history for one LocalCoder task."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from copy import deepcopy
import json
from typing import Any

from config import MAX_DYNAMIC_MESSAGES, MAX_TOOL_OUTPUT_CHARS
from tools.base import OUTPUT_TRUNCATION_MARKER, truncate_text


class ContextManager:
    """Retain permanent instructions and a bounded recent dynamic history."""

    def __init__(
        self,
        system_prompt: str,
        task: str,
        max_dynamic_messages: int = MAX_DYNAMIC_MESSAGES,
        max_tool_output_chars: int = MAX_TOOL_OUTPUT_CHARS,
    ) -> None:
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("system_prompt must be a non-empty string")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")
        if (
            isinstance(max_dynamic_messages, bool)
            or not isinstance(max_dynamic_messages, int)
            or max_dynamic_messages < 2
        ):
            raise ValueError("max_dynamic_messages must be an integer of at least 2")
        if (
            isinstance(max_tool_output_chars, bool)
            or not isinstance(max_tool_output_chars, int)
            or max_tool_output_chars <= len(OUTPUT_TRUNCATION_MARKER)
        ):
            raise ValueError(
                "max_tool_output_chars must be an integer longer than the "
                "truncation marker"
            )

        self._permanent = (
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        )
        self._groups: deque[list[dict[str, Any]]] = deque()
        self._dynamic_count = 0
        self._max_dynamic_messages = max_dynamic_messages
        self._max_tool_output_chars = max_tool_output_chars

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Return a detached provider-ready message list."""

        dynamic = [
            deepcopy(message)
            for group in self._groups
            for message in group
        ]
        return [deepcopy(message) for message in self._permanent] + dynamic

    @property
    def dynamic_message_count(self) -> int:
        return self._dynamic_count

    def add(self, message: dict[str, Any]) -> None:
        """Add one dynamic message."""

        self.add_group([message])

    def add_group(self, messages: Iterable[dict[str, Any]]) -> None:
        """Add one assistant turn atomically, preserving tool-call pairing."""

        group = [self._prepare(message) for message in messages]
        if not group:
            return
        group = self._fit_oversized_group(group)
        self._groups.append(group)
        self._dynamic_count += len(group)
        while (
            self._dynamic_count > self._max_dynamic_messages
            and len(self._groups) > 1
        ):
            removed = self._groups.popleft()
            self._dynamic_count -= len(removed)

    def _prepare(self, message: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(message, dict):
            raise TypeError("message must be a dictionary")
        prepared = deepcopy(message)
        if prepared.get("role") == "tool":
            content = prepared.get("content")
            if isinstance(content, str):
                prepared["content"] = self._truncate_tool_content(content)
        return prepared

    def _truncate_tool_content(self, content: str) -> str:
        if len(content) <= self._max_tool_output_chars:
            return content
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return truncate_text(content, self._max_tool_output_chars)[0]
        if not isinstance(payload, dict):
            return truncate_text(content, self._max_tool_output_chars)[0]

        fields = [
            name
            for name in ("output", "error")
            if isinstance(payload.get(name), str)
        ]
        if not fields:
            return truncate_text(content, self._max_tool_output_chars)[0]
        field = max(fields, key=lambda name: len(payload[name]))
        original = payload[field]
        low = len(OUTPUT_TRUNCATION_MARKER) + 1
        high = len(original) - 1
        best: str | None = None
        while low <= high:
            candidate_limit = (low + high) // 2
            payload[field] = truncate_text(original, candidate_limit)[0]
            rendered = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            if len(rendered) <= self._max_tool_output_chars:
                best = rendered
                low = candidate_limit + 1
            else:
                high = candidate_limit - 1
        payload[field] = original
        if best is not None:
            return best
        return truncate_text(content, self._max_tool_output_chars)[0]

    def _fit_oversized_group(
        self,
        group: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if len(group) <= self._max_dynamic_messages:
            return group
        first = group[0]
        if first.get("role") != "assistant" or self._max_dynamic_messages == 1:
            return group[-self._max_dynamic_messages :]

        kept = [first] + group[-(self._max_dynamic_messages - 1) :]
        kept_ids = {
            message.get("tool_call_id")
            for message in kept[1:]
            if message.get("role") == "tool"
        }
        if "tool_calls" in first:
            first["tool_calls"] = [
                call
                for call in first["tool_calls"]
                if call.get("id") in kept_ids
            ]
        return kept
