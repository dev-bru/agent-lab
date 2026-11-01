"""Check the small bridge between local tools and model tool calls."""

import asyncio
from types import SimpleNamespace

from fastmcp import Client

from agent_lab import mcp_server, tools_schema


S = {"type": "object", "properties": {"a": {"type": "number"},
                                      "b": {"type": "integer"}, "c": {}},
     "required": ["a", "b"]}


def test_real_tools_use_their_input_schemas() -> None:
    """Keep each of the nine local tool schemas as supplied by FastMCP."""
    async def list_tools():
        """List tools from the server in memory."""
        async with Client(mcp_server.mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(list_tools())
    assert len(tools) == 9
    for tool in tools:
        result = tools_schema.to_openai(tool)
        assert result["type"] == "function"
        assert result["function"]["name"] == tool.name
        assert result["function"]["description"] == tool.description
        assert result["function"]["parameters"] is tool.input_schema
        if tool.name == "multiply":
            assert result["function"]["parameters"]["required"] == ["a", "b"]


def test_missing_description_is_empty() -> None:
    """Offer a tool even when it has no description."""
    tool = SimpleNamespace(name="sample", description=None, input_schema={})
    assert tools_schema.to_openai(tool)["function"]["description"] == ""


def test_check_args_accepts_numbers_and_untyped_values() -> None:
    """Accept valid numbers and a value without a schema type."""
    assert tools_schema.check_args(S, {"a": 1.5, "b": 2}) == []
    assert tools_schema.check_args(S, {"a": 1, "b": 2, "c": "anything"}) == []


def test_check_args_reports_missing_then_unknown() -> None:
    """Give missing names first and unknown names next."""
    assert tools_schema.check_args(S, {"c": 1, "d": 2}) == [
        "missing argument 'a'", "missing argument 'b'", "unknown argument 'd'"]


def test_check_args_rejects_wrong_number_types() -> None:
    """Reject text and booleans where numbers are needed."""
    for value, name in [("x", "str"), (True, "bool")]:
        assert tools_schema.check_args(S, {"a": value, "b": 2}) == [
            f"argument 'a' must be number, got {name}"]


def test_check_args_rejects_wrong_integer_types() -> None:
    """Reject floats and booleans where an integer is needed."""
    for value, name in [(1.5, "float"), (True, "bool")]:
        assert tools_schema.check_args(S, {"a": 1, "b": value}) == [
            f"argument 'b' must be integer, got {name}"]


def test_check_args_needs_an_object() -> None:
    """Reject JSON values that cannot name tool arguments."""
    for value in (5, [1]):
        assert tools_schema.check_args(S, value) == ["arguments must be a JSON object"]


def test_check_args_checks_other_simple_types_in_order() -> None:
    """Check the remaining JSON types and keep problem order."""
    schema = {"properties": {name: {"type": kind} for name, kind in [
        ("s", "string"), ("flag", "boolean"), ("obj", "object"),
        ("items", "array"), ("empty", "null")]}}
    assert tools_schema.check_args(schema, {"s": "x", "flag": False, "obj": {},
                                           "items": [], "empty": None}) == []
    assert tools_schema.check_args(schema, {"flag": 0, "s": 1, "other": 3}) == [
        "unknown argument 'other'", "argument 'flag' must be boolean, got int",
        "argument 's' must be string, got int"]
