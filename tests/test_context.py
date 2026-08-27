from copy import deepcopy
import json

import pytest

from context import ContextManager


def test_context_keeps_permanent_messages_and_bounds_dynamic_history() -> None:
    context = ContextManager(
        system_prompt="permanent system",
        task="permanent task",
        max_dynamic_messages=3,
    )

    for index in range(5):
        context.add({"role": "assistant", "content": f"dynamic-{index}"})

    assert context.messages == [
        {"role": "system", "content": "permanent system"},
        {"role": "user", "content": "permanent task"},
        {"role": "assistant", "content": "dynamic-2"},
        {"role": "assistant", "content": "dynamic-3"},
        {"role": "assistant", "content": "dynamic-4"},
    ]
    assert context.dynamic_message_count == 3


def test_context_truncates_tool_output_with_useful_beginning_and_end() -> None:
    context = ContextManager(
        system_prompt="system",
        task="task",
        max_tool_output_chars=80,
    )
    original = {
        "role": "tool",
        "tool_call_id": "call-long",
        "content": "BEGIN-" + ("x" * 200) + "-END",
    }
    untouched = deepcopy(original)

    context.add(original)

    content = context.messages[-1]["content"]
    assert len(content) == 80
    assert content.startswith("BEGIN-")
    assert content.endswith("-END")
    assert "[output truncated]" in content
    assert original == untouched


def test_context_does_not_truncate_non_tool_messages() -> None:
    context = ContextManager(
        system_prompt="system",
        task="task",
        max_tool_output_chars=40,
    )
    long_text = "a" * 100

    context.add({"role": "assistant", "content": long_text})

    assert context.messages[-1]["content"] == long_text


def test_context_keeps_truncated_json_tool_observation_parseable() -> None:
    context = ContextManager(
        system_prompt="system",
        task="task",
        max_tool_output_chars=160,
    )
    payload = {
        "success": True,
        "output": "BEGIN-" + ("x" * 500) + "-END",
        "error": None,
        "metadata": {"exit_code": 0},
    }

    context.add(
        {
            "role": "tool",
            "tool_call_id": "call-json",
            "content": json.dumps(payload, sort_keys=True),
        }
    )

    content = context.messages[-1]["content"]
    parsed = json.loads(content)
    assert len(content) <= 160
    assert parsed["output"].startswith("BEGIN-")
    assert parsed["output"].endswith("-END")
    assert "[output truncated]" in parsed["output"]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("max_dynamic_messages", 0),
        ("max_dynamic_messages", 1),
        ("max_tool_output_chars", 20),
        ("max_dynamic_messages", True),
    ],
)
def test_context_rejects_invalid_limits(name: str, value: object) -> None:
    arguments = {name: value}

    with pytest.raises(ValueError):
        ContextManager("system", "task", **arguments)  # type: ignore[arg-type]
