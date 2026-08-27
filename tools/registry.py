"""Registration, schema exposure, validation, and dispatch for local tools."""

from collections.abc import Callable
from dataclasses import dataclass
import inspect
from typing import Any

from tools.base import ToolResult

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
