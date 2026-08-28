from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from todo import (  # noqa: E402
    add_todo,
    complete_todo,
    list_todos,
    main,
)


def test_add_assigns_incrementing_ids_and_persists(tmp_path: Path) -> None:
    data_file = tmp_path / "todos.json"

    first = add_todo(data_file, "Write tests")
    second = add_todo(data_file, "Implement feature")

    assert first == {"id": 1, "title": "Write tests", "completed": False}
    assert second == {"id": 2, "title": "Implement feature", "completed": False}
    assert list_todos(data_file) == [first, second]


def test_complete_marks_only_requested_todo(tmp_path: Path) -> None:
    data_file = tmp_path / "todos.json"
    add_todo(data_file, "First")
    add_todo(data_file, "Second")

    assert complete_todo(data_file, 2) is True
    assert complete_todo(data_file, 99) is False
    assert list_todos(data_file) == [
        {"id": 1, "title": "First", "completed": False},
        {"id": 2, "title": "Second", "completed": True},
    ]


def test_list_command_renders_completion_state(
    tmp_path: Path,
    capsys: object,
) -> None:
    data_file = tmp_path / "todos.json"
    add_todo(data_file, "First")
    add_todo(data_file, "Second")
    complete_todo(data_file, 2)

    exit_code = main(["--data-file", str(data_file), "list"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "1. [ ] First\n2. [x] Second\n"
    assert captured.err == ""


def test_add_command_reports_created_id(
    tmp_path: Path,
    capsys: object,
) -> None:
    data_file = tmp_path / "todos.json"

    assert main(["--data-file", str(data_file), "add", "CLI todo"]) == 0

    captured = capsys.readouterr()
    assert captured.out == "Added todo 1.\n"
    assert captured.err == ""
    assert list_todos(data_file) == [
        {"id": 1, "title": "CLI todo", "completed": False}
    ]


def test_complete_command_reports_success_and_missing_id(
    tmp_path: Path,
    capsys: object,
) -> None:
    data_file = tmp_path / "todos.json"
    add_todo(data_file, "Complete through CLI")

    assert main(["--data-file", str(data_file), "complete", "1"]) == 0
    success = capsys.readouterr()
    assert success.out == "Completed todo 1.\n"
    assert success.err == ""

    assert main(["--data-file", str(data_file), "complete", "99"]) == 1
    missing = capsys.readouterr()
    assert missing.out == ""
    assert missing.err == "Todo 99 not found.\n"
