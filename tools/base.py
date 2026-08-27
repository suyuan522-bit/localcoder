"""Shared local-tool result types."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolResult:
    """A consistent success or failure result returned by every tool."""

    success: bool
    output: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
