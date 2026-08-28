"""Workspace-scoped Git diff with a non-repository fallback."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
import subprocess

from config import MAX_TOOL_OUTPUT_CHARS
from tools.base import OUTPUT_TRUNCATION_MARKER, ToolResult, truncate_text
from tools.workspace import Workspace


def get_diff(
    workspace: Workspace,
    modified_files: Iterable[str] | None = None,
) -> ToolResult:
    """Return a bounded Git diff scoped to one workspace."""

    known_files = set(modified_files or ())
    repository_hint = _nearest_git_root(workspace.root)
    command_prefix = ["git"]
    if repository_hint is not None:
        command_prefix.extend(["-c", f"safe.directory={repository_hint}"])

    try:
        repository_result = subprocess.run(
            [
                *command_prefix,
                "-C",
                str(workspace.root),
                "rev-parse",
                "--show-toplevel",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return _fallback("Git executable is unavailable.", sorted(known_files))

    if repository_result.returncode != 0:
        return _fallback(
            "Workspace is not inside a Git repository.",
            sorted(known_files),
        )

    repository_root = Path(repository_result.stdout.strip()).resolve()
    try:
        workspace_pathspec = workspace.root.relative_to(repository_root)
    except ValueError:
        return ToolResult(
            success=False,
            error="Git repository root does not contain the workspace.",
            metadata={
                "git_repository": True,
                "changed_files": sorted(known_files),
                "output_truncated": False,
            },
        )

    pathspec = workspace_pathspec.as_posix() or "."
    try:
        diff_code, diff_output, diff_truncated = _run_git_bounded(
            [
                *command_prefix,
                "-C",
                str(repository_root),
                "diff",
                "HEAD",
                "--no-ext-diff",
                "--no-color",
                "--",
                pathspec,
            ],
            MAX_TOOL_OUTPUT_CHARS,
        )
        if diff_code != 0:
            diff_code, diff_output, diff_truncated = _diff_without_head(
                command_prefix,
                repository_root,
                pathspec,
            )
        untracked_code, untracked_output, untracked_truncated = _run_git_bounded(
            [
                *command_prefix,
                "-C",
                str(repository_root),
                "ls-files",
                "--others",
                "--exclude-standard",
                "--",
                pathspec,
            ],
            MAX_TOOL_OUTPUT_CHARS,
        )
    except OSError:
        return _fallback("Git executable is unavailable.", sorted(known_files))

    if diff_code != 0:
        return _git_failure("Git diff", diff_code, sorted(known_files))
    if untracked_code != 0:
        return _git_failure(
            "Git untracked-file discovery",
            untracked_code,
            sorted(known_files),
        )

    untracked_files = _workspace_relative_untracked(
        untracked_output,
        workspace_pathspec,
        truncated=untracked_truncated,
    )
    known_files.update(untracked_files)
    sections: list[str] = []
    if diff_output:
        sections.append(diff_output if diff_truncated else diff_output.rstrip())
    if untracked_files:
        rendered = "\n".join(f"- {path}" for path in untracked_files)
        sections.append(f"Untracked files:\n{rendered}")
    if untracked_truncated:
        sections.append("Additional untracked files were omitted.")

    changed_files = sorted(known_files)
    output = "\n\n".join(sections)
    if not output:
        output = _known_files_message(
            "No tracked or untracked Git changes for the workspace.",
            changed_files,
        )
    output, final_truncated = truncate_text(output, MAX_TOOL_OUTPUT_CHARS)
    return ToolResult(
        success=True,
        output=output,
        metadata={
            "git_repository": True,
            "changed_files": changed_files,
            "output_truncated": (
                diff_truncated or untracked_truncated or final_truncated
            ),
        },
    )


def _diff_without_head(
    command_prefix: Sequence[str],
    repository_root: Path,
    pathspec: str,
) -> tuple[int, str, bool]:
    """Collect index and worktree changes in a repository with no HEAD."""

    sections: list[str] = []
    truncated = False
    for extra_arguments in (("--cached",), ()):
        code, output, part_truncated = _run_git_bounded(
            [
                *command_prefix,
                "-C",
                str(repository_root),
                "diff",
                *extra_arguments,
                "--no-ext-diff",
                "--no-color",
                "--",
                pathspec,
            ],
            MAX_TOOL_OUTPUT_CHARS,
        )
        if code != 0:
            return code, output, part_truncated
        if output:
            sections.append(output.rstrip())
        truncated = truncated or part_truncated
    combined, final_truncated = truncate_text(
        "\n\n".join(sections),
        MAX_TOOL_OUTPUT_CHARS,
    )
    return 0, combined, truncated or final_truncated


def _run_git_bounded(
    command: Sequence[str],
    max_chars: int,
) -> tuple[int, str, bool]:
    """Run Git while retaining at most a bounded prefix and suffix in memory."""

    if max_chars <= len(OUTPUT_TRUNCATION_MARKER):
        raise ValueError("max_chars must be longer than the truncation marker")
    process = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.stdout is None:
        raise OSError("Git subprocess did not provide an output stream.")

    available = max_chars - len(OUTPUT_TRUNCATION_MARKER)
    head_size = available // 2
    tail_size = available - head_size
    prefix = ""
    tail = ""
    total_chars = 0
    while True:
        chunk = process.stdout.read(4096)
        if not chunk:
            break
        total_chars += len(chunk)
        if len(prefix) < max_chars + 1:
            remaining = max_chars + 1 - len(prefix)
            prefix += chunk[:remaining]
        tail = (tail + chunk)[-tail_size:]

    return_code = process.wait()
    if total_chars <= max_chars:
        return return_code, prefix[:total_chars], False
    return (
        return_code,
        prefix[:head_size] + OUTPUT_TRUNCATION_MARKER + tail,
        True,
    )


def _workspace_relative_untracked(
    output: str,
    workspace_pathspec: Path,
    *,
    truncated: bool = False,
) -> list[str]:
    prefix = workspace_pathspec.as_posix()
    files: list[str] = []
    repository_paths = output.splitlines()
    if truncated and OUTPUT_TRUNCATION_MARKER in output:
        head, tail = output.split(OUTPUT_TRUNCATION_MARKER, 1)
        head_paths = head.splitlines()
        tail_paths = tail.splitlines()
        repository_paths = head_paths[:-1] + tail_paths[1:]
    for repository_relative in repository_paths:
        if not repository_relative:
            continue
        path = Path(repository_relative)
        if prefix and prefix != ".":
            try:
                path = path.relative_to(workspace_pathspec)
            except ValueError:
                continue
        files.append(path.as_posix())
    return sorted(set(files))


def _git_failure(
    operation: str,
    return_code: int,
    changed_files: list[str],
) -> ToolResult:
    return ToolResult(
        success=False,
        error=f"{operation} failed with exit code {return_code}.",
        metadata={
            "git_repository": True,
            "changed_files": changed_files,
            "output_truncated": False,
        },
    )


def _nearest_git_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _fallback(reason: str, changed_files: list[str]) -> ToolResult:
    output = _known_files_message(reason, changed_files)
    output, output_truncated = truncate_text(output, MAX_TOOL_OUTPUT_CHARS)
    return ToolResult(
        success=True,
        output=output,
        metadata={
            "git_repository": False,
            "changed_files": changed_files,
            "output_truncated": output_truncated,
        },
    )


def _known_files_message(reason: str, changed_files: list[str]) -> str:
    rendered_files = (
        "\n".join(f"- {path}" for path in changed_files)
        if changed_files
        else "(none)"
    )
    return f"{reason}\nKnown modified files:\n{rendered_files}"
