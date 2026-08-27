"""Workspace-root validation shared by file-oriented tools."""

from pathlib import Path


class WorkspaceBoundaryError(ValueError):
    """Raised when a requested path resolves outside the workspace root."""


class Workspace:
    """Resolve paths while enforcing a single workspace boundary."""

    def __init__(self, root: str | Path) -> None:
        resolved_root = Path(root).expanduser().resolve()
        if not resolved_root.is_dir():
            raise ValueError(f"Workspace root must be an existing directory: {resolved_root}")
        self.root = resolved_root

    def resolve(self, requested_path: str | Path = ".") -> Path:
        """Return a normalized path if it remains inside the workspace."""

        requested = Path(requested_path).expanduser()
        candidate = requested if requested.is_absolute() else self.root / requested
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceBoundaryError(
                f"Path resolves outside workspace: {requested_path}"
            ) from exc
        return resolved

    def relative(self, path: str | Path) -> str:
        """Return a workspace-relative POSIX-style path after validation."""

        return self.resolve(path).relative_to(self.root).as_posix() or "."
