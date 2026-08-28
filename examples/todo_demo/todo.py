"""Small file-backed Todo CLI used by the LocalCoder demonstration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections.abc import Sequence
import sys
from typing import Any


def list_todos(data_file: str | Path) -> list[dict[str, Any]]:
    path = Path(data_file)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Todo data must be a JSON list.")
    return data


def add_todo(data_file: str | Path, title: str) -> dict[str, Any]:
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Todo title must be a non-empty string.")
    todos = list_todos(data_file)
    todo = {
        "id": max((item["id"] for item in todos), default=0) + 1,
        "title": title.strip(),
        "completed": False,
    }
    todos.append(todo)
    _save_todos(data_file, todos)
    return todo


def complete_todo(data_file: str | Path, todo_id: int) -> bool:
    todos = list_todos(data_file)
    for todo in todos:
        if todo["id"] == todo_id:
            todo["completed"] = True
            _save_todos(data_file, todos)
            return True
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a small Todo list.")
    parser.add_argument(
        "--data-file",
        default="todos.json",
        help="JSON file used to persist todos.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    add_parser = commands.add_parser("add", help="Add a todo.")
    add_parser.add_argument("title")
    commands.add_parser("list", help="List todos.")
    complete_parser = commands.add_parser("complete", help="Complete a todo.")
    complete_parser.add_argument("todo_id", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "add":
        todo = add_todo(args.data_file, args.title)
        print(f"Added todo {todo['id']}.")
        return 0
    if args.command == "list":
        for todo in list_todos(args.data_file):
            marker = "x" if todo["completed"] else " "
            print(f"{todo['id']}. [{marker}] {todo['title']}")
        return 0
    if complete_todo(args.data_file, args.todo_id):
        print(f"Completed todo {args.todo_id}.")
        return 0
    print(f"Todo {args.todo_id} not found.", file=sys.stderr)
    return 1


def _save_todos(
    data_file: str | Path,
    todos: list[dict[str, Any]],
) -> None:
    path = Path(data_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(todos, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


if __name__ == "__main__":
    raise SystemExit(main())
