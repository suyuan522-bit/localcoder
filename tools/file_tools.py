"""Bounded text-file tools operating inside one validated workspace."""

from collections.abc import Iterator
from pathlib import Path

from config import (
    LIST_FILES_MAX_ENTRIES,
    MAX_TOOL_OUTPUT_CHARS,
    MAX_WRITE_FILE_CHARS,
    READ_FILE_MAX_LINES,
    SEARCH_MAX_MATCHES,
)
from tools.base import ToolResult, truncate_text
from tools.workspace import Workspace, WorkspaceBoundaryError

IGNORED_NAMES = {".git", ".pytest_cache", ".venv", "venv", "__pycache__"}


def _failure(error: str, **metadata: object) -> ToolResult:
    return ToolResult(success=False, error=error, metadata=dict(metadata))


def _bounded_output(text: str) -> tuple[str, bool]:
    return truncate_text(text, MAX_TOOL_OUTPUT_CHARS)


def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    data = path.read_bytes()
    if b"\x00" in data:
        raise ValueError(f"Cannot read binary file: {path}")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"File is not valid UTF-8 text: {path}") from exc


def _iter_files(
    root: Path,
    workspace: Workspace,
    visited_directories: set[Path] | None = None,
) -> Iterator[Path]:
    if visited_directories is None:
        visited_directories = set()
    resolved_root = workspace.resolve(root)
    if root.is_file():
        yield root
        return
    if resolved_root in visited_directories:
        return
    visited_directories.add(resolved_root)
    for child in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if child.name in IGNORED_NAMES:
            continue
        try:
            workspace.resolve(child)
        except WorkspaceBoundaryError:
            continue
        if child.is_dir():
            yield from _iter_files(child, workspace, visited_directories)
        elif child.is_file():
            yield child


def list_files(
    workspace: Workspace,
    path: str = ".",
    max_depth: int = 2,
) -> ToolResult:
    """List a bounded, deterministic workspace tree."""

    if not isinstance(path, str):
        return _failure("path must be a string")
    if not isinstance(max_depth, int) or max_depth < 0:
        return _failure("max_depth must be a non-negative integer", path=path)
    try:
        root = workspace.resolve(path)
        if not root.exists():
            return _failure(f"Path not found: {path}", path=path)
        if root.is_file():
            relative = workspace.relative(root)
            return ToolResult(
                success=True,
                output=relative,
                metadata={"path": path, "entries": 1, "truncated": False},
            )
        if not root.is_dir():
            return _failure(f"Path is not a directory: {path}", path=path)

        entries: list[str] = []
        truncated = False
        output_chars = 0

        def walk(directory: Path, depth: int) -> None:
            nonlocal truncated, output_chars
            if depth > max_depth or truncated:
                return
            for child in sorted(directory.iterdir(), key=lambda item: item.name.casefold()):
                if child.name in IGNORED_NAMES:
                    continue
                try:
                    workspace.resolve(child)
                except WorkspaceBoundaryError:
                    continue
                relative = workspace.relative(child)
                rendered = relative + ("/" if child.is_dir() else "")
                added_chars = len(rendered) + (1 if entries else 0)
                if (
                    len(entries) >= LIST_FILES_MAX_ENTRIES
                    or output_chars + added_chars > MAX_TOOL_OUTPUT_CHARS
                ):
                    truncated = True
                    return
                entries.append(rendered)
                output_chars += added_chars
                if child.is_dir() and depth < max_depth:
                    walk(child, depth + 1)
                    if truncated:
                        return

        if max_depth > 0:
            walk(root, 1)
        output = "\n".join(entries)
        if truncated:
            output = f"{output}\n[entries truncated]" if output else "[entries truncated]"
        return ToolResult(
            success=True,
            output=output,
            metadata={"path": path, "entries": len(entries), "truncated": truncated},
        )
    except (WorkspaceBoundaryError, OSError) as exc:
        return _failure(str(exc), path=path)


def read_file(
    workspace: Workspace,
    path: str,
    start_line: int = 1,
    end_line: int | None = None,
) -> ToolResult:
    """Read at most 200 numbered lines from a UTF-8 text file."""

    if not isinstance(path, str):
        return _failure("path must be a string")
    if not isinstance(start_line, int) or start_line < 1:
        return _failure("start_line must be an integer greater than or equal to 1", path=path)
    if end_line is not None and (not isinstance(end_line, int) or end_line < start_line):
        return _failure("end_line must be an integer greater than or equal to start_line", path=path)
    try:
        target = workspace.resolve(path)
        text = _read_text(target)
        lines = text.splitlines()
        relative = workspace.relative(target)
        if start_line > len(lines):
            return _failure(
                f"start_line {start_line} exceeds file length {len(lines)}",
                path=relative,
                line_count=len(lines),
            )
        requested_end = end_line if end_line is not None else start_line + READ_FILE_MAX_LINES - 1
        effective_end = min(requested_end, start_line + READ_FILE_MAX_LINES - 1)
        selected = lines[start_line - 1 : effective_end]
        rendered = "\n".join(
            f"{number}: {line}"
            for number, line in enumerate(selected, start=start_line)
        )
        rendered, output_truncated = _bounded_output(rendered)
        actual_end = start_line + len(selected) - 1
        truncated = output_truncated or len(lines) > actual_end
        return ToolResult(
            success=True,
            output=rendered,
            metadata={
                "path": relative,
                "start_line": start_line,
                "end_line": actual_end,
                "truncated": truncated,
            },
        )
    except (WorkspaceBoundaryError, FileNotFoundError, ValueError, OSError) as exc:
        return _failure(str(exc), path=path)


def search_text(workspace: Workspace, query: str, path: str = ".") -> ToolResult:
    """Search recursively for a literal string with bounded results."""

    if not isinstance(path, str):
        return _failure("path must be a string")
    if not isinstance(query, str) or not query:
        return _failure("query must be a non-empty string", path=path)
    try:
        root = workspace.resolve(path)
        if not root.exists():
            return _failure(f"Path not found: {path}", path=path)
        matches: list[str] = []
        output_chars = 0
        truncated = False
        for file_path in _iter_files(root, workspace):
            try:
                text = _read_text(file_path)
            except (FileNotFoundError, ValueError, OSError):
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if query not in line:
                    continue
                concise_line = line.strip()
                if len(concise_line) > 500:
                    concise_line = concise_line[:497] + "..."
                rendered = f"{workspace.relative(file_path)}:{line_number}: {concise_line}"
                added_chars = len(rendered) + (1 if matches else 0)
                if (
                    len(matches) >= SEARCH_MAX_MATCHES
                    or output_chars + added_chars > MAX_TOOL_OUTPUT_CHARS
                ):
                    truncated = True
                    break
                matches.append(rendered)
                output_chars += added_chars
            if truncated:
                break
        output = "\n".join(matches)
        if truncated:
            output = f"{output}\n[matches truncated]" if output else "[matches truncated]"
        return ToolResult(
            success=True,
            output=output,
            metadata={"query": query, "matches": len(matches), "truncated": truncated},
        )
    except (WorkspaceBoundaryError, OSError) as exc:
        return _failure(str(exc), path=path)


def write_file(
    workspace: Workspace,
    path: str,
    content: str,
    modified_files: set[str] | None = None,
) -> ToolResult:
    """Create or fully replace a reasonably sized UTF-8 text file."""

    if not isinstance(path, str):
        return _failure("path must be a string")
    if not isinstance(content, str):
        return _failure("content must be a string", path=path)
    if len(content) > MAX_WRITE_FILE_CHARS:
        return _failure(
            f"content exceeds maximum size of {MAX_WRITE_FILE_CHARS} characters",
            path=path,
        )
    try:
        target = workspace.resolve(path)
        if target.exists() and target.is_dir():
            return _failure(f"Path is a directory: {path}", path=path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))
        relative = workspace.relative(target)
        if modified_files is not None:
            modified_files.add(relative)
        return ToolResult(
            success=True,
            output=f"Wrote {relative}",
            metadata={"path": relative, "characters": len(content)},
        )
    except (WorkspaceBoundaryError, OSError) as exc:
        return _failure(str(exc), path=path)


def replace_text(
    workspace: Workspace,
    path: str,
    old_text: str,
    new_text: str,
    modified_files: set[str] | None = None,
) -> ToolResult:
    """Replace exactly one unambiguous literal text occurrence."""

    if not isinstance(path, str):
        return _failure("path must be a string")
    if not isinstance(old_text, str):
        return _failure("old_text must be a string", path=path)
    if not old_text:
        return _failure("old_text must be a non-empty string", path=path)
    if not isinstance(new_text, str):
        return _failure("new_text must be a string", path=path)
    try:
        target = workspace.resolve(path)
        text = _read_text(target)
        occurrences = text.count(old_text)
        if occurrences == 0:
            return _failure(
                "Replacement target not found; read the latest file before retrying",
                path=path,
                occurrences=0,
            )
        if occurrences > 1:
            return _failure(
                f"Replacement target appears {occurrences} times; provide a unique exact target",
                path=path,
                occurrences=occurrences,
            )
        updated = text.replace(old_text, new_text, 1)
        target.write_bytes(updated.encode("utf-8"))
        relative = workspace.relative(target)
        if modified_files is not None:
            modified_files.add(relative)
        return ToolResult(
            success=True,
            output=f"Replaced text in {relative}",
            metadata={"path": relative, "occurrences": 1},
        )
    except (WorkspaceBoundaryError, FileNotFoundError, ValueError, OSError) as exc:
        return _failure(str(exc), path=path)
