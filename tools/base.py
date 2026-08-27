"""Shared local-tool result types."""

from dataclasses import dataclass, field
from typing import Any

OUTPUT_TRUNCATION_MARKER = "\n[output truncated]\n"


@dataclass(slots=True)
class ToolResult:
    """A consistent success or failure result returned by every tool."""

    success: bool
    output: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def truncate_text(
    text: str,
    max_chars: int,
    marker: str = OUTPUT_TRUNCATION_MARKER,
) -> tuple[str, bool]:
    """Bound text while preserving useful beginning and ending portions."""

    if len(text) <= max_chars:
        return text, False
    if max_chars <= len(marker):
        raise ValueError("max_chars must be longer than the truncation marker")
    available = max_chars - len(marker)
    head_size = available // 2
    tail_size = available - head_size
    return text[:head_size] + marker + text[-tail_size:], True
