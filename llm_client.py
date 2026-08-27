"""OpenAI-compatible chat client with normalized native tool calls."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import json
import math
import time
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from config import LLMConfig


TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)


class LLMClientError(RuntimeError):
    """A sanitized, user-facing LLM provider failure."""


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Provider-independent native tool call."""

    id: str
    name: str
    arguments: dict[str, Any] | None
    argument_error: str | None = None


@dataclass(slots=True)
class LLMResponse:
    """Provider-independent assistant response for later AgentCore use."""

    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient:
    """Send chat messages and native tool schemas to an OpenAI-compatible API."""

    def __init__(
        self,
        config: LLMConfig,
        *,
        client: Any | None = None,
        max_retries: int = 2,
        retry_base_delay_seconds: float = 0.25,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if (
            isinstance(max_retries, bool)
            or not isinstance(max_retries, int)
            or max_retries < 0
        ):
            raise ValueError("max_retries must be a non-negative integer")
        if (
            isinstance(retry_base_delay_seconds, bool)
            or not isinstance(retry_base_delay_seconds, (int, float))
            or not math.isfinite(retry_base_delay_seconds)
            or retry_base_delay_seconds < 0
        ):
            raise ValueError(
                "retry_base_delay_seconds must be a finite non-negative number"
            )

        self._model = config.model
        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._sleep = sleep
        self._client = client or OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            max_retries=0,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Return assistant text and normalized native tool calls."""

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if tools is not None:
            payload["tools"] = tools

        response = self._request(payload)
        return _normalize_response(response)

    def _request(self, payload: dict[str, Any]) -> Any:
        for retry_number in range(self._max_retries + 1):
            try:
                return self._client.chat.completions.create(**payload)
            except TRANSIENT_EXCEPTIONS as exc:
                if retry_number >= self._max_retries:
                    attempts = retry_number + 1
                    raise LLMClientError(
                        "Transient LLM request failed after "
                        f"{attempts} attempts ({type(exc).__name__})."
                    ) from None
                delay = self._retry_base_delay_seconds * (2**retry_number)
                self._sleep(delay)
            except Exception as exc:
                raise LLMClientError(
                    f"LLM request failed ({type(exc).__name__})."
                ) from None

        raise AssertionError("bounded retry loop ended unexpectedly")


def _normalize_response(response: Any) -> LLMResponse:
    choices = _field(response, "choices")
    if not choices:
        raise LLMClientError("LLM response did not include an assistant choice.")

    message = _field(choices[0], "message")
    if message is None:
        raise LLMClientError("LLM response choice did not include a message.")

    raw_text = _field(message, "content")
    text = raw_text if isinstance(raw_text, str) else None
    raw_tool_calls = _field(message, "tool_calls") or []
    tool_calls = [_normalize_tool_call(call) for call in raw_tool_calls]
    return LLMResponse(text=text, tool_calls=tool_calls)


def _normalize_tool_call(raw_call: Any) -> ToolCall:
    call_id = _field(raw_call, "id")
    function = _field(raw_call, "function")
    name = _field(function, "name") if function is not None else None
    raw_arguments = _field(function, "arguments") if function is not None else None

    if not isinstance(call_id, str) or not call_id:
        raise LLMClientError("LLM response contained a tool call without an ID.")
    if not isinstance(name, str) or not name:
        raise LLMClientError("LLM response contained a tool call without a name.")

    arguments, argument_error = _parse_arguments(raw_arguments)
    return ToolCall(
        id=call_id,
        name=name,
        arguments=arguments,
        argument_error=argument_error,
    )


def _parse_arguments(
    raw_arguments: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    if isinstance(raw_arguments, Mapping):
        return dict(raw_arguments), None

    try:
        parsed = json.loads(raw_arguments)
    except (TypeError, json.JSONDecodeError):
        return None, "Tool arguments are not valid JSON."

    if not isinstance(parsed, dict):
        return None, "Tool arguments must decode to an object."
    return parsed, None


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)
