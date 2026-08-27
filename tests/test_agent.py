from copy import deepcopy
from io import StringIO
import json
import os
import shlex
import subprocess
import sys
from typing import Any

import pytest

import main as cli
from agent import AgentCore, AgentRunResult, AgentState
from llm_client import LLMClientError, LLMResponse, ToolCall
from tools.base import ToolResult
from tools.registry import ToolRegistry, register_local_tools
from tools.workspace import Workspace
from trace_logger import TraceLogger


class FakeLLMClient:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = iter(outcomes)
        self.requests: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self.requests.append(
            {"messages": deepcopy(messages), "tools": deepcopy(tools)}
        )
        outcome = next(self._outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, LLMResponse)
        return outcome


def test_agent_state_initializes_required_runtime_fields() -> None:
    state = AgentState(task="Fix the failing tests")

    assert state.task == "Fix the failing tests"
    assert state.step_count == 0
    assert state.modified_files == set()
    assert state.verification_runs == []
    assert state.last_error is None
    assert state.last_edit_step is None
    assert state.finished is False


def test_agent_dispatches_read_then_finishes_explicitly() -> None:
    registry = ToolRegistry()
    registry.register(
        "read_file",
        "Read one file.",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        lambda path: ToolResult(
            success=True,
            output=f"1: contents of {path}",
            metadata={"path": path},
        ),
    )
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-read",
                        name="read_file",
                        arguments={"path": "README.md"},
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-finish",
                        name="finish",
                        arguments={
                            "summary": "Inspected the requested file.",
                            "verification": "Read completed successfully.",
                            "limitations": None,
                        },
                    )
                ]
            ),
        ]
    )
    agent = AgentCore(
        llm_client=fake,
        registry=registry,
        task="Inspect README.md",
        max_steps=4,
    )
    agent.state.modified_files.add("notes.txt")

    result = agent.run()

    assert result == AgentRunResult(
        success=True,
        message=(
            "Summary: Inspected the requested file.\n"
            "Changed files: notes.txt\n"
            "Verification: Read completed successfully."
        ),
    )
    assert agent.state.step_count == 2
    assert agent.state.finished is True
    assert agent.state.final_summary == "Inspected the requested file."
    assert agent.state.final_verification == "Read completed successfully."
    assert agent.state.final_limitations is None
    assert len(fake.requests) == 2

    first_request = fake.requests[0]
    assert [message["role"] for message in first_request["messages"]] == [
        "system",
        "user",
    ]
    assert first_request["messages"][1]["content"] == "Inspect README.md"
    assert {tool["function"]["name"] for tool in first_request["tools"]} == {
        "read_file",
        "finish",
    }

    second_messages = fake.requests[1]["messages"]
    assert second_messages[-2] == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call-read",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": '{"path": "README.md"}',
                },
            }
        ],
    }
    assert second_messages[-1]["role"] == "tool"
    assert second_messages[-1]["tool_call_id"] == "call-read"
    assert json.loads(second_messages[-1]["content"]) == {
        "error": None,
        "metadata": {"path": "README.md"},
        "output": "1: contents of README.md",
        "success": True,
    }


def test_agent_feeds_failure_back_then_recovers_with_multiple_tool_calls() -> None:
    registry = ToolRegistry()
    registry.register(
        "echo",
        "Echo a value.",
        {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        lambda value: ToolResult(success=True, output=value),
    )
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(id="call-missing", name="missing", arguments={})
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-one",
                        name="echo",
                        arguments={"value": "one"},
                    ),
                    ToolCall(
                        id="call-two",
                        name="echo",
                        arguments={"value": "two"},
                    ),
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-finish",
                        name="finish",
                        arguments={
                            "summary": "Recovered.",
                            "verification": "Echo calls succeeded.",
                        },
                    )
                ]
            ),
        ]
    )
    agent = AgentCore(fake, registry, "Recover from a tool error", max_steps=5)

    result = agent.run()

    assert result.success is True
    assert agent.state.step_count == 3
    assert agent.state.last_error == "Unknown tool: missing"

    failure_observation = json.loads(
        fake.requests[1]["messages"][-1]["content"]
    )
    assert failure_observation["success"] is False
    assert failure_observation["error"] == "Unknown tool: missing"

    recovery_messages = fake.requests[2]["messages"]
    recovery_observations = [
        json.loads(message["content"])
        for message in recovery_messages
        if message["role"] == "tool"
        and message["tool_call_id"] in {"call-one", "call-two"}
    ]
    assert [observation["output"] for observation in recovery_observations] == [
        "one",
        "two",
    ]


def test_agent_returns_malformed_arguments_as_tool_observation() -> None:
    dispatched = False
    registry = ToolRegistry()

    def should_not_run() -> ToolResult:
        nonlocal dispatched
        dispatched = True
        return ToolResult(success=True)

    registry.register(
        "noop",
        "Do nothing.",
        {"type": "object", "additionalProperties": False},
        should_not_run,
    )
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-bad",
                        name="noop",
                        arguments=None,
                        argument_error="Tool arguments are not valid JSON.",
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-finish",
                        name="finish",
                        arguments={
                            "summary": "Handled invalid arguments.",
                            "verification": "Observed controlled failure.",
                        },
                    )
                ]
            ),
        ]
    )
    agent = AgentCore(fake, registry, "Handle malformed arguments", max_steps=3)

    result = agent.run()

    assert result.success is True
    assert dispatched is False
    observation = json.loads(fake.requests[1]["messages"][-1]["content"])
    assert observation == {
        "error": "Tool arguments are not valid JSON.",
        "metadata": {
            "error_type": "invalid_tool_arguments",
            "tool": "noop",
        },
        "output": "",
        "success": False,
    }


def test_finish_must_be_the_only_tool_call_in_its_response() -> None:
    calls: list[str] = []
    registry = ToolRegistry()
    registry.register(
        "echo",
        "Echo a value.",
        {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        lambda value: (
            calls.append(value)
            or ToolResult(success=True, output=value)
        ),
    )
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-mixed-finish",
                        name="finish",
                        arguments={
                            "summary": "Too early.",
                            "verification": "Not a standalone call.",
                        },
                    ),
                    ToolCall(
                        id="call-echo",
                        name="echo",
                        arguments={"value": "still executed"},
                    ),
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-final-finish",
                        name="finish",
                        arguments={
                            "summary": "Finished separately.",
                            "verification": "Echo succeeded.",
                        },
                    )
                ]
            ),
        ]
    )
    agent = AgentCore(fake, registry, "Handle a mixed finish batch", max_steps=3)

    result = agent.run()

    assert result.success is True
    assert agent.state.step_count == 2
    assert calls == ["still executed"]
    first_batch_observations = [
        message
        for message in fake.requests[1]["messages"]
        if message["role"] == "tool"
        and message["tool_call_id"] in {"call-mixed-finish", "call-echo"}
    ]
    assert len(first_batch_observations) == 2
    rejected_finish = json.loads(first_batch_observations[0]["content"])
    assert rejected_finish["success"] is False
    assert rejected_finish["error"] == (
        "finish must be the only tool call in an assistant response"
    )
    assert json.loads(first_batch_observations[1]["content"])["output"] == (
        "still executed"
    )


def test_assistant_text_does_not_finish_and_max_steps_is_controlled() -> None:
    fake = FakeLLMClient(
        [
            LLMResponse(text="The task is done."),
            LLMResponse(text="Everything is complete."),
        ]
    )
    agent = AgentCore(
        fake,
        ToolRegistry(),
        "Do not trust text-only completion",
        max_steps=2,
    )

    result = agent.run()

    assert result.success is False
    assert result.message == "Agent stopped after reaching MAX_STEPS (2)."
    assert agent.state.step_count == 2
    assert agent.state.finished is False
    assert len(fake.requests) == 2


def test_unrecoverable_llm_error_returns_controlled_failure() -> None:
    fake = FakeLLMClient([LLMClientError("Provider unavailable.")])
    agent = AgentCore(fake, ToolRegistry(), "Try one request")

    result = agent.run()

    assert result == AgentRunResult(
        success=False,
        message="Provider unavailable.",
    )
    assert agent.state.step_count == 1
    assert agent.state.last_error == "Provider unavailable."
    assert agent.state.finished is False


def test_keyboard_interrupt_returns_controlled_failure() -> None:
    fake = FakeLLMClient([KeyboardInterrupt()])
    agent = AgentCore(fake, ToolRegistry(), "Interrupt this run")

    result = agent.run()

    assert result == AgentRunResult(
        success=False,
        message="Agent interrupted by user.",
    )
    assert agent.state.step_count == 1
    assert agent.state.last_error == "Agent interrupted by user."


@pytest.mark.parametrize("max_steps", [0, -1, True, 1.5])
def test_max_steps_must_be_a_positive_integer(max_steps: object) -> None:
    with pytest.raises(ValueError):
        AgentCore(
            FakeLLMClient([]),
            ToolRegistry(),
            "Validate MAX_STEPS",
            max_steps=max_steps,  # type: ignore[arg-type]
        )


def test_registered_local_tools_write_file_and_share_modified_state(
    tmp_path: Any,
) -> None:
    registry = ToolRegistry()
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-write",
                        name="write_file",
                        arguments={"path": "result.txt", "content": "done\n"},
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-finish",
                        name="finish",
                        arguments={
                            "summary": "Created result.txt.",
                            "verification": "File write returned success.",
                            "limitations": "No command verification was available in this focused test.",
                        },
                    )
                ]
            ),
        ]
    )
    agent = AgentCore(fake, registry, "Create result.txt")
    register_local_tools(
        registry,
        Workspace(tmp_path),
        agent.state.modified_files,
    )

    result = agent.run()

    assert result.success is True
    assert (tmp_path / "result.txt").read_text(encoding="utf-8") == "done\n"
    assert agent.state.modified_files == {"result.txt"}
    assert "Changed files: result.txt" in result.message
    assert {tool["function"]["name"] for tool in registry.definitions()} == {
        "list_files",
        "read_file",
        "search_text",
        "write_file",
        "replace_text",
        "run_command",
        "finish",
    }


def test_finish_requires_successful_verification_after_edit(tmp_path: Any) -> None:
    registry = ToolRegistry()
    command = _python_command("print('verified')")
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-write",
                        name="write_file",
                        arguments={"path": "module.py", "content": "value = 1\n"},
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-early-finish",
                        name="finish",
                        arguments={
                            "summary": "Too early.",
                            "verification": "Not actually run.",
                        },
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-verify",
                        name="run_command",
                        arguments={"command": command},
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-finish",
                        name="finish",
                        arguments={
                            "summary": "Verified edit.",
                            "verification": "Verification command exited with code 0.",
                        },
                    )
                ]
            ),
        ]
    )
    agent = AgentCore(fake, registry, "Edit then verify", max_steps=5)
    register_local_tools(registry, Workspace(tmp_path), agent.state.modified_files)

    result = agent.run()

    assert result.success is True
    assert agent.state.last_edit_step == 1
    assert agent.state.verification_runs[0]["command"] == command
    assert agent.state.verification_runs[0]["step"] == 3
    assert agent.state.verification_runs[0]["exit_code"] == 0
    assert agent.state.verification_runs[0]["success"] is True
    early_finish = json.loads(fake.requests[2]["messages"][-1]["content"])
    assert early_finish["success"] is False
    assert early_finish["metadata"]["error_type"] == "verification_required"
    assert "run_command" in early_finish["error"]


def test_finish_allows_explicit_verification_limitation_after_edit(tmp_path: Any) -> None:
    registry = ToolRegistry()
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-write",
                        name="write_file",
                        arguments={"path": "module.py", "content": "value = 1\n"},
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-finish",
                        name="finish",
                        arguments={
                            "summary": "Edited module.",
                            "verification": "No verification command was run.",
                            "limitations": "The required runtime is unavailable.",
                        },
                    )
                ]
            ),
        ]
    )
    agent = AgentCore(fake, registry, "Edit without available runtime")
    register_local_tools(registry, Workspace(tmp_path), agent.state.modified_files)

    result = agent.run()

    assert result.success is True
    assert agent.state.final_limitations == "The required runtime is unavailable."


def test_verification_before_later_edit_in_same_step_does_not_cover_edit(
    tmp_path: Any,
) -> None:
    registry = ToolRegistry()
    command = _python_command("print('verified too early')")
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-verify-first",
                        name="run_command",
                        arguments={"command": command},
                    ),
                    ToolCall(
                        id="call-edit-second",
                        name="write_file",
                        arguments={"path": "module.py", "content": "value = 1\n"},
                    ),
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-early-finish",
                        name="finish",
                        arguments={
                            "summary": "Too early.",
                            "verification": "The command ran before the edit.",
                        },
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-limited-finish",
                        name="finish",
                        arguments={
                            "summary": "Stopped with an explicit limitation.",
                            "verification": "The edit was not verified.",
                            "limitations": "No later verification could be run.",
                        },
                    )
                ]
            ),
        ]
    )
    agent = AgentCore(fake, registry, "Verify ordering", max_steps=4)
    register_local_tools(registry, Workspace(tmp_path), agent.state.modified_files)

    result = agent.run()

    assert result.success is True
    rejected = json.loads(fake.requests[2]["messages"][-1]["content"])
    assert rejected["metadata"]["error_type"] == "verification_required"


def test_edit_failed_verification_fix_successful_verification_then_finish(
    tmp_path: Any,
) -> None:
    secret = "sk-test-secret-must-not-appear"
    trace_output = StringIO()
    registry = ToolRegistry()
    verify_command = _python_module_command("py_compile", "module.py")
    broken = "def broken(:\n    return '" + secret + "'\n"
    fixed = "def fixed():\n    return 'ok'\n"
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-write",
                        name="write_file",
                        arguments={"path": "module.py", "content": broken},
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-failed-verify",
                        name="run_command",
                        arguments={"command": verify_command},
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-fix",
                        name="replace_text",
                        arguments={
                            "path": "module.py",
                            "old_text": broken,
                            "new_text": fixed,
                        },
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-success-verify",
                        name="run_command",
                        arguments={"command": verify_command},
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-finish",
                        name="finish",
                        arguments={
                            "summary": "Fixed module syntax.",
                            "verification": "py_compile exited with code 0.",
                        },
                    )
                ]
            ),
        ]
    )
    agent = AgentCore(
        fake,
        registry,
        "Repair module.py",
        trace_logger=TraceLogger(stream=trace_output, secrets=[secret]),
    )
    register_local_tools(registry, Workspace(tmp_path), agent.state.modified_files)

    result = agent.run()

    assert result.success is True
    assert (tmp_path / "module.py").read_text(encoding="utf-8") == fixed
    assert agent.state.last_edit_step == 3
    assert [run["success"] for run in agent.state.verification_runs] == [False, True]
    assert [run["step"] for run in agent.state.verification_runs] == [2, 4]
    assert [run["exit_code"] for run in agent.state.verification_runs] == [1, 0]
    rendered_trace = trace_output.getvalue()
    assert "Step 1 · EDIT" in rendered_trace
    assert "Step 2 · VERIFY" in rendered_trace
    assert "Step 3 · EDIT" in rendered_trace
    assert "Step 4 · VERIFY" in rendered_trace
    assert "Step 5 · DONE" in rendered_trace
    assert "Changed files: module.py" in rendered_trace
    assert "Final verification: SUCCESS" in rendered_trace
    assert secret not in rendered_trace


@pytest.mark.parametrize(
    "command",
    ["set", "powershell -Command Get-ChildItem Env:"],
)
def test_trace_does_not_print_run_command_environment_output(command: str) -> None:
    trace_output = StringIO()
    secret = "ordinary-environment-value-not-matching-token-patterns"
    logger = TraceLogger(stream=trace_output)

    logger.log_tool(
        step=1,
        tool_name="run_command",
        arguments={"command": command},
        result=ToolResult(
            success=True,
            output=f"HARMLESS_NAME={secret}",
            metadata={
                "exit_code": 0,
                "timed_out": False,
                "output_truncated": False,
            },
        ),
        changed_files=set(),
        verification_runs=[],
        verification_current=True,
    )

    rendered = trace_output.getvalue()
    assert secret not in rendered
    assert "exit_code=0" in rendered
    assert "output_chars=" in rendered


def test_cli_runs_real_agent_composition_with_fake_llm(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-finish",
                        name="finish",
                        arguments={
                            "summary": "CLI completed.",
                            "verification": "Fake client supplied finish.",
                        },
                    )
                ]
            )
        ]
    )
    monkeypatch.setenv("LLM_API_KEY", "fake-cli-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setattr(cli, "LLMClient", lambda config: fake)

    exit_code = cli.main(
        ["--workspace", str(tmp_path), "--task", "Finish from the CLI"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Summary: CLI completed." in captured.out
    assert captured.err == ""


def test_cli_reports_configuration_error_without_starting_agent(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)

    exit_code = cli.main(
        ["--workspace", str(tmp_path), "--task", "Cannot start"]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "Missing required environment variables" in captured.err


def _python_command(code: str) -> str:
    arguments = [sys.executable, "-c", code]
    return (
        subprocess.list2cmdline(arguments)
        if os.name == "nt"
        else shlex.join(arguments)
    )


def _python_module_command(module: str, path: str) -> str:
    arguments = [sys.executable, "-m", module, path]
    return (
        subprocess.list2cmdline(arguments)
        if os.name == "nt"
        else shlex.join(arguments)
    )
