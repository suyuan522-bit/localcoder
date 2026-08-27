from pathlib import Path

import pytest

from tools.workspace import Workspace, WorkspaceBoundaryError


def test_resolve_returns_normalized_path_inside_workspace(tmp_path: Path) -> None:
    nested = tmp_path / "src" / "package"
    nested.mkdir(parents=True)
    workspace = Workspace(tmp_path)

    assert workspace.resolve("src/../src/package") == nested.resolve()


def test_resolve_rejects_parent_traversal_outside_workspace(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)

    with pytest.raises(WorkspaceBoundaryError, match="outside workspace"):
        workspace.resolve("../outside.txt")


def test_resolve_rejects_absolute_path_outside_workspace(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)
    outside = tmp_path.parent / "outside.txt"

    with pytest.raises(WorkspaceBoundaryError, match="outside workspace"):
        workspace.resolve(outside)


def test_resolve_accepts_absolute_path_inside_workspace(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)
    inside = tmp_path / "nested" / "file.txt"

    assert workspace.resolve(inside) == inside.resolve()


def test_workspace_requires_an_existing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(ValueError, match="existing directory"):
        Workspace(missing)
