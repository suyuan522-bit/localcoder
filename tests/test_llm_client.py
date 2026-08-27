from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import llm_client
from config import ConfigurationError, LLMConfig, load_llm_config
from llm_client import LLMClient, LLMClientError, LLMResponse, ToolCall


class FakeCompletions:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = iter(outcomes)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        outcome = next(self._outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes: list[object]) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(outcomes))


def assistant_response(
    content: str | None = None,
    tool_calls: list[object] | None = None,
) -> object:
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def native_tool_call(call_id: str, name: str, arguments: str) -> object:
    function = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(id=call_id, type="function", function=function)


def config(secret: str = "test-secret") -> LLMConfig:
    return LLMConfig(
        api_key=secret,
        base_url="https://llm.example/v1",
        model="test-model",
    )


def test_load_llm_config_reads_required_environment() -> None:
    result = load_llm_config(
        {
            "LLM_API_KEY": "  key-from-env  ",
            "LLM_BASE_URL": " https://llm.example/v1 ",
            "LLM_MODEL": " test-model ",
        }
    )

    assert result == LLMConfig(
        api_key="key-from-env",
        base_url="https://llm.example/v1",
        model="test-model",
    )
    assert "key-from-env" not in repr(result)


@pytest.mark.parametrize("missing_name", ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"])
def test_load_llm_config_fails_fast_without_leaking_values(missing_name: str) -> None:
    secret = "sk-never-show-this"
    environment = {
        "LLM_API_KEY": secret,
        "LLM_BASE_URL": "https://llm.example/v1",
        "LLM_MODEL": "test-model",
    }
    environment[missing_name] = "   "

    with pytest.raises(ConfigurationError) as caught:
        load_llm_config(environment)

    assert missing_name in str(caught.value)
    assert secret not in str(caught.value)


def test_complete_sends_messages_and_tools_and_normalizes_assistant_text() -> None:
    provider_response = assistant_response(content="I inspected the workspace.")
    fake = FakeClient([provider_response])
    client = LLMClient(config(), client=fake)
    messages = [{"role": "user", "content": "Inspect the workspace."}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    result = client.complete(messages, tools)

    assert result == LLMResponse(text="I inspected the workspace.", tool_calls=[])
    assert fake.chat.completions.calls == [
        {"model": "test-model", "messages": messages, "tools": tools}
    ]


def test_default_client_uses_environment_configuration_and_disables_sdk_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    fake = FakeClient([assistant_response(content="ok")])

    def build_client(**kwargs: object) -> FakeClient:
        captured.update(kwargs)
        return fake

    monkeypatch.setattr(llm_client, "OpenAI", build_client)

    client = LLMClient(config("local-test-key"))

    assert client.complete([], []).text == "ok"
    assert captured == {
        "api_key": "local-test-key",
        "base_url": "https://llm.example/v1",
        "max_retries": 0,
    }


def test_complete_normalizes_multiple_native_tool_calls() -> None:
    provider_response = assistant_response(
        tool_calls=[
            native_tool_call("call-1", "read_file", '{"path": "README.md"}'),
            native_tool_call("call-2", "run_command", '{"command": "pytest -q"}'),
        ]
    )
    client = LLMClient(config(), client=FakeClient([provider_response]))

    result = client.complete([], [])

    assert result == LLMResponse(
        text=None,
        tool_calls=[
            ToolCall(
                id="call-1",
                name="read_file",
                arguments={"path": "README.md"},
            ),
            ToolCall(
                id="call-2",
                name="run_command",
                arguments={"command": "pytest -q"},
            ),
        ],
    )


def test_malformed_tool_arguments_are_preserved_as_controlled_failure() -> None:
    provider_response = assistant_response(
        tool_calls=[native_tool_call("call-bad", "read_file", "{not-json")]
    )
    client = LLMClient(config(), client=FakeClient([provider_response]))

    result = client.complete([], [])

    assert result.tool_calls == [
        ToolCall(
            id="call-bad",
            name="read_file",
            arguments=None,
            argument_error="Tool arguments are not valid JSON.",
        )
    ]


def test_non_object_tool_arguments_are_rejected_predictably() -> None:
    provider_response = assistant_response(
        tool_calls=[native_tool_call("call-list", "read_file", "[]")]
    )
    client = LLMClient(config(), client=FakeClient([provider_response]))

    result = client.complete([], [])

    assert result.tool_calls[0].arguments is None
    assert result.tool_calls[0].argument_error == (
        "Tool arguments must decode to an object."
    )


def test_transient_failure_retries_with_a_bounded_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TemporaryProviderError(Exception):
        pass

    monkeypatch.setattr(llm_client, "TRANSIENT_EXCEPTIONS", (TemporaryProviderError,))
    fake = FakeClient(
        [
            TemporaryProviderError("temporary-1"),
            TemporaryProviderError("temporary-2"),
            assistant_response(content="recovered"),
        ]
    )
    delays: list[float] = []
    client = LLMClient(
        config(),
        client=fake,
        max_retries=2,
        retry_base_delay_seconds=0.1,
        sleep=delays.append,
    )

    result = client.complete([], [])

    assert result.text == "recovered"
    assert len(fake.chat.completions.calls) == 3
    assert delays == [0.1, 0.2]


def test_retry_exhaustion_is_bounded_and_sanitizes_provider_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "sk-secret-from-provider-error"

    class TemporaryProviderError(Exception):
        pass

    monkeypatch.setattr(llm_client, "TRANSIENT_EXCEPTIONS", (TemporaryProviderError,))
    fake = FakeClient(
        [TemporaryProviderError(secret), TemporaryProviderError(secret)]
    )
    client = LLMClient(
        config(secret),
        client=fake,
        max_retries=1,
        retry_base_delay_seconds=0,
        sleep=lambda _: None,
    )

    with pytest.raises(LLMClientError) as caught:
        client.complete([], [])

    assert len(fake.chat.completions.calls) == 2
    assert "2 attempts" in str(caught.value)
    assert secret not in str(caught.value)
    assert secret not in caplog.text


def test_non_transient_provider_error_is_not_retried_or_leaked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "sk-secret-from-error"
    fake = FakeClient([RuntimeError(f"request failed with {secret}")])
    client = LLMClient(config(secret), client=fake, max_retries=3)

    with pytest.raises(LLMClientError) as caught:
        client.complete([], [])

    assert len(fake.chat.completions.calls) == 1
    assert "RuntimeError" in str(caught.value)
    assert secret not in str(caught.value)
    assert secret not in caplog.text


@pytest.mark.parametrize(
    ("max_retries", "delay"),
    [
        (-1, 0.1),
        (True, 0.1),
        (1.5, 0.1),
        (1, -0.1),
        (1, True),
        (1, float("inf")),
        (1, float("nan")),
    ],
)
def test_retry_configuration_rejects_invalid_values(
    max_retries: object,
    delay: object,
) -> None:
    with pytest.raises(ValueError):
        LLMClient(
            config(),
            client=FakeClient([]),
            max_retries=max_retries,  # type: ignore[arg-type]
            retry_base_delay_seconds=delay,  # type: ignore[arg-type]
        )
