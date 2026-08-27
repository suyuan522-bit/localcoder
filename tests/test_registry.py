from tools.base import ToolResult
from tools.registry import ToolRegistry


def test_tool_result_metadata_is_not_shared() -> None:
    first = ToolResult(success=True, output="one")
    second = ToolResult(success=True, output="two")

    first.metadata["changed"] = True

    assert second.metadata == {}


def test_registry_exposes_native_tool_definition_and_dispatches() -> None:
    registry = ToolRegistry()

    def greet(name: str) -> ToolResult:
        return ToolResult(success=True, output=f"hello {name}")

    parameters = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "additionalProperties": False,
    }
    registry.register("greet", "Greet one person.", parameters, greet)

    assert registry.definitions() == [
        {
            "type": "function",
            "function": {
                "name": "greet",
                "description": "Greet one person.",
                "parameters": parameters,
            },
        }
    ]
    assert registry.dispatch("greet", {"name": "Ada"}) == ToolResult(
        success=True,
        output="hello Ada",
    )


def test_registry_returns_failure_for_unknown_tool() -> None:
    result = ToolRegistry().dispatch("missing", {})

    assert result.success is False
    assert result.error == "Unknown tool: missing"
    assert result.metadata == {"tool": "missing", "error_type": "unknown_tool"}


def test_registry_rejects_non_object_arguments() -> None:
    registry = ToolRegistry()
    registry.register("noop", "No operation.", {"type": "object"}, lambda: ToolResult(True))

    result = registry.dispatch("noop", ["not", "an", "object"])

    assert result.success is False
    assert result.metadata["error_type"] == "invalid_arguments"


def test_registry_converts_signature_error_to_failure() -> None:
    registry = ToolRegistry()
    registry.register(
        "needs_name",
        "Needs a name.",
        {"type": "object"},
        lambda name: ToolResult(True, output=name),
    )

    result = registry.dispatch("needs_name", {})

    assert result.success is False
    assert result.metadata["error_type"] == "invalid_arguments"
    assert "Invalid arguments" in (result.error or "")


def test_registry_converts_unexpected_tool_exception_to_failure() -> None:
    registry = ToolRegistry()

    def explode() -> ToolResult:
        raise RuntimeError("boom")

    registry.register("explode", "Raise an error.", {"type": "object"}, explode)

    result = registry.dispatch("explode", {})

    assert result.success is False
    assert result.error == "Tool 'explode' failed: boom"
    assert result.metadata == {"tool": "explode", "error_type": "tool_exception"}


def test_registry_rejects_duplicate_registration() -> None:
    registry = ToolRegistry()
    registry.register("noop", "No operation.", {"type": "object"}, lambda: ToolResult(True))

    try:
        registry.register("noop", "Duplicate.", {"type": "object"}, lambda: ToolResult(True))
    except ValueError as exc:
        assert str(exc) == "Tool already registered: noop"
    else:
        raise AssertionError("duplicate tool registration should fail")
