"""Bounded local command execution for verification tasks."""

import os
import re
import shlex
import signal
import subprocess

from config import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    MAX_COMMAND_TIMEOUT_SECONDS,
    MAX_TOOL_OUTPUT_CHARS,
)
from tools.base import ToolResult
from tools.workspace import Workspace

_OUTPUT_TRUNCATION_MARKER = "\n[output truncated]\n"


def _is_dangerous(command: str) -> bool:
    for segment in re.split(r"&&|\|\||[;&|]", command):
        try:
            tokens = [token.strip("\"'") for token in shlex.split(segment, posix=False)]
        except ValueError:
            tokens = segment.split()
        if not tokens:
            continue
        executable = re.split(r"[\\/]", tokens[0].casefold())[-1]
        arguments = [token.casefold() for token in tokens[1:]]

        if executable == "rm":
            flags = "".join(
                argument.lstrip("-")
                for argument in arguments
                if argument.startswith("-") and argument != "--"
            )
            operands = [argument for argument in arguments if not argument.startswith("-")]
            if "r" in flags and "f" in flags and "/" in operands:
                return True
        elif executable.startswith("mkfs"):
            return True
        elif executable in {"shutdown", "reboot"}:
            return True
        elif executable in {"format", "format.com"}:
            if any(argument.startswith("c:") for argument in arguments):
                return True
        elif executable == "del":
            switches = {argument for argument in arguments if argument.startswith("/")}
            targets = [argument for argument in arguments if not argument.startswith("/")]
            if {"/s", "/q"}.issubset(switches) and any(
                target in {"c:\\", "c:/"} for target in targets
            ):
                return True
    return False


def _format_output(stdout: str, stderr: str) -> str:
    sections: list[str] = []
    if stdout:
        sections.append(f"STDOUT:\n{stdout.rstrip()}")
    if stderr:
        sections.append(f"STDERR:\n{stderr.rstrip()}")
    return "\n".join(sections) if sections else "(no output)"


def _truncate_output(output: str) -> tuple[str, bool]:
    if len(output) <= MAX_TOOL_OUTPUT_CHARS:
        return output, False
    available = MAX_TOOL_OUTPUT_CHARS - len(_OUTPUT_TRUNCATION_MARKER)
    head_size = available // 2
    tail_size = available - head_size
    return (
        output[:head_size] + _OUTPUT_TRUNCATION_MARKER + output[-tail_size:],
        True,
    )


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


def run_command(
    workspace: Workspace,
    command: str,
    timeout: int | float | None = None,
) -> ToolResult:
    """Run a command in the workspace with best-effort execution controls."""

    if not isinstance(command, str) or not command.strip():
        return ToolResult(success=False, error="command must be a non-empty string")
    if _is_dangerous(command):
        return ToolResult(
            success=False,
            error="Command rejected by dangerous-command guard",
            metadata={
                "exit_code": None,
                "timed_out": False,
                "rejected": True,
                "output_truncated": False,
            },
        )

    requested_timeout = DEFAULT_COMMAND_TIMEOUT_SECONDS if timeout is None else timeout
    if not isinstance(requested_timeout, (int, float)) or requested_timeout <= 0:
        return ToolResult(success=False, error="timeout must be a positive number")
    effective_timeout = min(requested_timeout, MAX_COMMAND_TIMEOUT_SECONDS)

    try:
        popen_options: dict[str, object] = {}
        if os.name == "nt":
            popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_options["start_new_session"] = True
        process = subprocess.Popen(
            command,
            cwd=workspace.root,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **popen_options,
        )
        try:
            stdout, stderr = process.communicate(timeout=effective_timeout)
        except subprocess.TimeoutExpired:
            _terminate_process_tree(process)
            stdout, stderr = process.communicate()
            output, output_truncated = _truncate_output(_format_output(stdout, stderr))
            return ToolResult(
                success=False,
                output=output,
                error=f"Command timed out after {effective_timeout} seconds",
                metadata={
                    "command": command,
                    "exit_code": None,
                    "timed_out": True,
                    "rejected": False,
                    "timeout_seconds": effective_timeout,
                    "output_truncated": output_truncated,
                },
            )
        output, output_truncated = _truncate_output(
            _format_output(stdout, stderr)
        )
        success = process.returncode == 0
        return ToolResult(
            success=success,
            output=output,
            error=None if success else f"Command exited with code {process.returncode}",
            metadata={
                "command": command,
                "exit_code": process.returncode,
                "timed_out": False,
                "rejected": False,
                "timeout_seconds": effective_timeout,
                "output_truncated": output_truncated,
            },
        )
    except OSError as exc:
        return ToolResult(
            success=False,
            error=f"Command could not be started: {exc}",
            metadata={
                "command": command,
                "exit_code": None,
                "timed_out": False,
                "rejected": False,
                "timeout_seconds": effective_timeout,
                "output_truncated": False,
            },
        )
