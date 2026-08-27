from pathlib import Path
import os
import subprocess

import pytest

from tools.file_tools import list_files, read_file, replace_text, search_text, write_file
from tools.workspace import Workspace


def test_list_files_respects_depth_and_ignores_noise(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("read me", encoding="utf-8")
    (tmp_path / "src" / "deep").mkdir(parents=True)
    (tmp_path / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "src" / "deep" / "data.txt").write_text("hidden by depth", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("noise", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cache.pyc").write_bytes(b"noise")

    result = list_files(Workspace(tmp_path), max_depth=2)

    assert result.success is True
    assert result.output.splitlines() == [
        "README.md",
        "src/",
        "src/app.py",
        "src/deep/",
    ]
    assert result.metadata == {"path": ".", "entries": 4, "truncated": False}


def test_list_files_caps_excessive_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    monkeypatch.setattr("tools.file_tools.LIST_FILES_MAX_ENTRIES", 2)

    result = list_files(Workspace(tmp_path))

    assert result.output.splitlines() == ["a.txt", "b.txt", "[entries truncated]"]
    assert result.metadata["truncated"] is True


def test_read_file_defaults_to_two_hundred_numbered_lines(tmp_path: Path) -> None:
    content = "\n".join(f"line {number}" for number in range(1, 206))
    (tmp_path / "large.txt").write_text(content, encoding="utf-8")

    result = read_file(Workspace(tmp_path), "large.txt")

    lines = result.output.splitlines()
    assert result.success is True
    assert len(lines) == 200
    assert lines[0] == "1: line 1"
    assert lines[-1] == "200: line 200"
    assert result.metadata == {
        "path": "large.txt",
        "start_line": 1,
        "end_line": 200,
        "truncated": True,
    }


def test_read_file_supports_an_explicit_bounded_range(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    result = read_file(Workspace(tmp_path), "notes.txt", start_line=2, end_line=3)

    assert result.output == "2: beta\n3: gamma"


def test_read_file_rejects_start_line_beyond_end_of_file(tmp_path: Path) -> None:
    (tmp_path / "short.txt").write_text("one\ntwo\n", encoding="utf-8")

    result = read_file(Workspace(tmp_path), "short.txt", start_line=3)

    assert result.success is False
    assert result.error == "start_line 3 exceeds file length 2"
    assert result.metadata == {"path": "short.txt", "line_count": 2}


@pytest.mark.parametrize(
    ("filename", "writer", "expected_error"),
    [
        ("missing.txt", None, "File not found"),
        ("binary.bin", lambda path: path.write_bytes(b"abc\x00def"), "binary file"),
    ],
)
def test_read_file_returns_descriptive_errors(
    tmp_path: Path,
    filename: str,
    writer: object,
    expected_error: str,
) -> None:
    if callable(writer):
        writer(tmp_path / filename)

    result = read_file(Workspace(tmp_path), filename)

    assert result.success is False
    assert expected_error in (result.error or "")


def test_search_text_reports_relative_file_line_and_content(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "one.py").write_text("first\nneedle here\n", encoding="utf-8")
    (tmp_path / "src" / "two.py").write_text("another needle\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored.txt").write_text("needle", encoding="utf-8")

    result = search_text(Workspace(tmp_path), "needle", "src")

    assert result.success is True
    assert result.output.splitlines() == [
        "src/one.py:2: needle here",
        "src/two.py:1: another needle",
    ]
    assert result.metadata == {"query": "needle", "matches": 2, "truncated": False}


def test_search_text_caps_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "many.txt").write_text("needle\nneedle\nneedle\n", encoding="utf-8")
    monkeypatch.setattr("tools.file_tools.SEARCH_MAX_MATCHES", 2)

    result = search_text(Workspace(tmp_path), "needle")

    assert result.output.splitlines()[-1] == "[matches truncated]"
    assert result.metadata == {"query": "needle", "matches": 2, "truncated": True}


def test_search_text_does_not_follow_directory_symlink_cycles(tmp_path: Path) -> None:
    (tmp_path / "match.txt").write_text("needle\n", encoding="utf-8")
    cycle = tmp_path / "cycle"
    try:
        cycle.symlink_to(tmp_path, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        if os.name != "nt":
            pytest.skip(f"directory symlinks unavailable: {exc}")
        junction = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(cycle), str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if junction.returncode != 0:
            pytest.skip(f"directory junctions unavailable: {junction.stderr}")

    result = search_text(Workspace(tmp_path), "needle")

    assert result.success is True
    assert result.output == "match.txt:1: needle"
    assert result.metadata == {"query": "needle", "matches": 1, "truncated": False}


def test_write_file_creates_parents_and_tracks_modified_path(tmp_path: Path) -> None:
    modified_files: set[str] = set()

    result = write_file(
        Workspace(tmp_path),
        "nested/new.txt",
        "hello\n",
        modified_files=modified_files,
    )

    assert result.success is True
    assert (tmp_path / "nested" / "new.txt").read_text(encoding="utf-8") == "hello\n"
    assert modified_files == {"nested/new.txt"}
    assert result.metadata["path"] == "nested/new.txt"


def test_write_file_preserves_requested_newline_bytes(tmp_path: Path) -> None:
    result = write_file(Workspace(tmp_path), "newlines.txt", "one\ntwo\n")

    assert result.success is True
    assert (tmp_path / "newlines.txt").read_bytes() == b"one\ntwo\n"


def test_replace_text_replaces_one_exact_match_and_tracks_file(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("before = 1\nafter = before\n", encoding="utf-8")
    modified_files: set[str] = set()

    result = replace_text(
        Workspace(tmp_path),
        "app.py",
        "before = 1",
        "before = 2",
        modified_files=modified_files,
    )

    assert result.success is True
    assert target.read_text(encoding="utf-8") == "before = 2\nafter = before\n"
    assert modified_files == {"app.py"}


def test_replace_text_rejects_missing_target_without_changing_file(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    result = replace_text(Workspace(tmp_path), "app.py", "value = 2", "value = 3")

    assert result.success is False
    assert "read the latest file" in (result.error or "")
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_replace_text_rejects_ambiguous_target_without_changing_file(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("same\nsame\n", encoding="utf-8")

    result = replace_text(Workspace(tmp_path), "app.py", "same", "different")

    assert result.success is False
    assert "appears 2 times" in (result.error or "")
    assert target.read_text(encoding="utf-8") == "same\nsame\n"


@pytest.mark.parametrize(
    "operation",
    [
        lambda workspace: list_files(workspace, 123),
        lambda workspace: read_file(workspace, 123),
        lambda workspace: search_text(workspace, "needle", 123),
        lambda workspace: write_file(workspace, 123, "content"),
        lambda workspace: replace_text(workspace, 123, "old", "new"),
    ],
)
def test_file_tools_return_controlled_failure_for_invalid_path_type(
    tmp_path: Path,
    operation: object,
) -> None:
    result = operation(Workspace(tmp_path))

    assert result.success is False
    assert result.error == "path must be a string"


def test_replace_text_returns_controlled_failure_for_invalid_text_type(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("value", encoding="utf-8")

    result = replace_text(Workspace(tmp_path), "app.py", 123, "new")

    assert result.success is False
    assert result.error == "old_text must be a string"


@pytest.mark.parametrize(
    "operation",
    [
        lambda workspace: list_files(workspace, ".."),
        lambda workspace: read_file(workspace, "../outside.txt"),
        lambda workspace: search_text(workspace, "needle", ".."),
        lambda workspace: write_file(workspace, "../outside.txt", "unsafe"),
        lambda workspace: replace_text(workspace, "../outside.txt", "a", "b"),
    ],
)
def test_file_tools_reject_paths_outside_workspace(tmp_path: Path, operation: object) -> None:
    result = operation(Workspace(tmp_path))

    assert result.success is False
    assert "outside workspace" in (result.error or "")
