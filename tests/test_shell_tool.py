import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

import pytest

from tools.shell_tool import _is_dangerous, run_command
from tools.workspace import Workspace


def _python_command(code: str) -> str:
    arguments = [sys.executable, "-c", code]
    return subprocess.list2cmdline(arguments) if os.name == "nt" else shlex.join(arguments)


def test_run_command_uses_workspace_and_captures_stdout(tmp_path: Path) -> None:
    command = _python_command("from pathlib import Path; print(Path.cwd().name)")

    result = run_command(Workspace(tmp_path), command)

    assert result.success is True
    assert tmp_path.name in result.output
    assert result.error is None
    assert result.metadata["exit_code"] == 0
    assert result.metadata["timed_out"] is False


def test_run_command_captures_stderr_and_nonzero_exit(tmp_path: Path) -> None:
    command = _python_command(
        "import sys; print('standard'); print('problem', file=sys.stderr); sys.exit(3)"
    )

    result = run_command(Workspace(tmp_path), command)

    assert result.success is False
    assert "standard" in result.output
    assert "problem" in result.output
    assert result.error == "Command exited with code 3"
    assert result.metadata["exit_code"] == 3


def test_run_command_times_out(tmp_path: Path) -> None:
    command = _python_command("import time; time.sleep(1)")

    result = run_command(Workspace(tmp_path), command, timeout=0.1)

    assert result.success is False
    assert result.error == "Command timed out after 0.1 seconds"
    assert result.metadata["exit_code"] is None
    assert result.metadata["timed_out"] is True


def test_run_command_timeout_terminates_child_process_tree(tmp_path: Path) -> None:
    marker = tmp_path / "child-finished.txt"
    child_code = (
        "import time; from pathlib import Path; "
        f"time.sleep(1); Path({str(marker)!r}).write_text('alive', encoding='utf-8')"
    )
    parent_code = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); time.sleep(5)"
    )

    result = run_command(Workspace(tmp_path), _python_command(parent_code), timeout=0.2)
    time.sleep(1.2)

    assert result.metadata["timed_out"] is True
    assert marker.exists() is False


def test_run_command_truncates_excessive_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tools.shell_tool.MAX_TOOL_OUTPUT_CHARS", 200)
    command = _python_command("print('x' * 500)")

    result = run_command(Workspace(tmp_path), command)

    assert result.success is True
    assert len(result.output) == 200
    assert "[output truncated]" in result.output
    assert result.metadata["output_truncated"] is True


def test_run_command_caps_requested_timeout(tmp_path: Path) -> None:
    result = run_command(Workspace(tmp_path), _python_command("print('ok')"), timeout=999)

    assert result.success is True
    assert result.metadata["timeout_seconds"] == 60


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "mkfs.ext4 /dev/sda",
        "shutdown /s",
        "reboot",
        "format C:",
        "del /s /q C:\\",
    ],
)
def test_run_command_rejects_obviously_dangerous_commands(
    tmp_path: Path,
    command: str,
) -> None:
    result = run_command(Workspace(tmp_path), command)

    assert result.success is False
    assert result.error == "Command rejected by dangerous-command guard"
    assert result.metadata["rejected"] is True
    assert result.metadata["exit_code"] is None


@pytest.mark.parametrize(
    "command",
    [
        "rm -fr /",
        "rm -r -f /",
        "del /q /s C:\\",
    ],
)
def test_dangerous_guard_recognizes_common_equivalent_spellings(command: str) -> None:
    assert _is_dangerous(command) is True


def test_run_command_does_not_dump_environment_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALCODER_TEST_SECRET", "do-not-print-this-value")

    result = run_command(Workspace(tmp_path), _python_command("print('safe output')"))

    assert result.success is True
    assert "safe output" in result.output
    assert "do-not-print-this-value" not in result.output


@pytest.mark.parametrize("command", ["", "   "])
def test_run_command_rejects_empty_command(tmp_path: Path, command: str) -> None:
    result = run_command(Workspace(tmp_path), command)

    assert result.success is False
    assert result.error == "command must be a non-empty string"
