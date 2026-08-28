from pathlib import Path
import subprocess

import pytest

from tools.git_tool import get_diff
from tools.workspace import Workspace


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repository}",
            "-C",
            str(repository),
            *arguments,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _initialize_repository(repository: Path) -> None:
    _git(repository, "init")
    _git(repository, "config", "user.name", "LocalCoder Test")
    _git(repository, "config", "user.email", "localcoder@example.invalid")


def test_get_diff_is_scoped_to_workspace(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    workspace_root = repository / "workspace"
    workspace_root.mkdir(parents=True)
    inside = workspace_root / "inside.py"
    outside = repository / "outside.py"
    inside.write_text("value = 1\n", encoding="utf-8")
    outside.write_text("outside = 1\n", encoding="utf-8")
    _initialize_repository(repository)
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "baseline")
    inside.write_text("value = 2\n", encoding="utf-8")
    outside.write_text("outside = 2\n", encoding="utf-8")

    result = get_diff(Workspace(workspace_root), {"inside.py"})

    assert result.success is True
    assert "+value = 2" in result.output
    assert "outside.py" not in result.output
    assert result.metadata == {
        "git_repository": True,
        "changed_files": ["inside.py"],
        "output_truncated": False,
    }


def test_get_diff_truncates_large_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    target = repository / "large.txt"
    target.write_text("before\n", encoding="utf-8")
    _initialize_repository(repository)
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "baseline")
    target.write_text("BEGIN\n" + ("x" * 500) + "\nEND\n", encoding="utf-8")
    monkeypatch.setattr("tools.git_tool.MAX_TOOL_OUTPUT_CHARS", 200)

    result = get_diff(Workspace(repository), {"large.txt"})

    assert result.success is True
    assert len(result.output) == 200
    assert "[output truncated]" in result.output
    assert result.metadata["output_truncated"] is True


def test_get_diff_includes_staged_changes(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    workspace_root = repository / "workspace"
    workspace_root.mkdir(parents=True)
    target = workspace_root / "staged.py"
    target.write_text("value = 1\n", encoding="utf-8")
    _initialize_repository(repository)
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "baseline")
    target.write_text("value = 2\n", encoding="utf-8")
    _git(repository, "add", "workspace/staged.py")

    result = get_diff(Workspace(workspace_root), {"staged.py"})

    assert result.success is True
    assert "+value = 2" in result.output
    assert result.metadata["git_repository"] is True


def test_get_diff_reports_only_workspace_untracked_files(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    workspace_root = repository / "workspace"
    workspace_root.mkdir(parents=True)
    _initialize_repository(repository)
    tracked = workspace_root / "tracked.py"
    tracked.write_text("tracked = True\n", encoding="utf-8")
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "baseline")
    (workspace_root / "new.py").write_text("new = True\n", encoding="utf-8")
    (repository / "outside-new.py").write_text(
        "outside = True\n",
        encoding="utf-8",
    )

    result = get_diff(Workspace(workspace_root))

    assert result.success is True
    assert "Untracked files:\n- new.py" in result.output
    assert "outside-new.py" not in result.output
    assert result.metadata["changed_files"] == ["new.py"]


def test_get_diff_never_reports_partial_untracked_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _initialize_repository(repository)
    (repository / "tracked.py").write_text("tracked = True\n", encoding="utf-8")
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "baseline")
    filenames = {
        f"file_{index:03d}_{'x' * 20}.txt" for index in range(40)
    }
    for filename in filenames:
        (repository / filename).write_text("new\n", encoding="utf-8")
    monkeypatch.setattr("tools.git_tool.MAX_TOOL_OUTPUT_CHARS", 200)

    result = get_diff(Workspace(repository))

    assert result.success is True
    assert result.metadata["output_truncated"] is True
    assert set(result.metadata["changed_files"]) <= filenames


def test_get_diff_falls_back_to_known_files_outside_git(tmp_path: Path) -> None:
    result = get_diff(
        Workspace(tmp_path),
        {"src/todo.py", "tests/test_todo.py"},
    )

    assert result.success is True
    assert result.output == (
        "Workspace is not inside a Git repository.\n"
        "Known modified files:\n"
        "- src/todo.py\n"
        "- tests/test_todo.py"
    )
    assert result.metadata == {
        "git_repository": False,
        "changed_files": ["src/todo.py", "tests/test_todo.py"],
        "output_truncated": False,
    }
