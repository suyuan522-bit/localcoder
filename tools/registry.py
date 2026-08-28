"""Registration, schema exposure, validation, and dispatch for local tools."""

from collections.abc import Callable
from dataclasses import dataclass
import inspect
from typing import Any

from tools.base import ToolResult
from tools.file_tools import (
    list_files,
    read_file,
    replace_text,
    search_text,
    write_file,
)
from tools.git_tool import get_diff
from tools.shell_tool import run_command
from tools.workspace import Workspace

ToolHandler = Callable[..., ToolResult]


@dataclass(frozen=True, slots=True)
class _RegisteredTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Keep AgentCore independent from individual tool implementations."""

    def __init__(self) -> None:
        self._tools: dict[str, _RegisteredTool] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: ToolHandler,
    ) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = _RegisteredTool(name, description, parameters, handler)

    def definitions(self) -> list[dict[str, Any]]:
        """Return native tool-calling compatible function schemas."""

        return [tool.definition() for tool in self._tools.values()]

    def dispatch(self, name: str, arguments: object) -> ToolResult:
        """Validate and call a registered tool without leaking exceptions."""

        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {name}",
                metadata={"tool": name, "error_type": "unknown_tool"},
            )
        if not isinstance(arguments, dict):
            return ToolResult(
                success=False,
                error=f"Invalid arguments for tool '{name}': expected an object",
                metadata={"tool": name, "error_type": "invalid_arguments"},
            )

        try:
            inspect.signature(tool.handler).bind(**arguments)
        except TypeError as exc:
            return ToolResult(
                success=False,
                error=f"Invalid arguments for tool '{name}': {exc}",
                metadata={"tool": name, "error_type": "invalid_arguments"},
            )

        try:
            result = tool.handler(**arguments)
            if not isinstance(result, ToolResult):
                raise TypeError("tool handler did not return ToolResult")
            return result
        except Exception as exc:  # Tool failures become controlled observations.
            return ToolResult(
                success=False,
                error=f"Tool '{name}' failed: {exc}",
                metadata={"tool": name, "error_type": "tool_exception"},
            )


def register_local_tools(
    registry: ToolRegistry,
    workspace: Workspace,
    modified_files: set[str],
) -> None:
    """Register the Phase 1 local tools for one agent task."""

    def handle_list_files(path: str = ".", max_depth: int = 2) -> ToolResult:
        return list_files(workspace, path, max_depth)

    def handle_read_file(
        path: str,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> ToolResult:
        return read_file(workspace, path, start_line, end_line)

    def handle_search_text(query: str, path: str = ".") -> ToolResult:
        return search_text(workspace, query, path)

    def handle_write_file(path: str, content: str) -> ToolResult:
        return write_file(workspace, path, content, modified_files)

    def handle_replace_text(
        path: str,
        old_text: str,
        new_text: str,
    ) -> ToolResult:
        return replace_text(
            workspace,
            path,
            old_text,
            new_text,
            modified_files,
        )

    def handle_run_command(
        command: str,
        timeout: int | float | None = None,
    ) -> ToolResult:
        return run_command(workspace, command, timeout)

    def handle_get_diff() -> ToolResult:
        return get_diff(workspace, modified_files)

    registry.register(
        "list_files",
        "List a bounded workspace tree.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."},
                "max_depth": {"type": "integer", "minimum": 0, "default": 2},
            },
            "additionalProperties": False,
        },
        handle_list_files,
    )
    registry.register(
        "read_file",
        "Read a bounded line range from a UTF-8 workspace file.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1, "default": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handle_read_file,
    )
    registry.register(
        "search_text",
        "Search for literal text in workspace files.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string", "default": "."},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handle_search_text,
    )
    registry.register(
        "write_file",
        "Create or fully replace a UTF-8 workspace file.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        handle_write_file,
    )
    registry.register(
        "replace_text",
        "Replace one unique exact text occurrence in a workspace file.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
            "additionalProperties": False,
        },
        handle_replace_text,
    )
    registry.register(
        "run_command",
        "Run a bounded command in the workspace.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "number", "exclusiveMinimum": 0},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        handle_run_command,
    )
    registry.register(
        "get_diff",
        "Show a bounded Git diff scoped to the workspace.",
        {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        handle_get_diff,
    )
