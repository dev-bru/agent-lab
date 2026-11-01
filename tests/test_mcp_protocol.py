"""Check the tools offered by the local MCP server."""

import asyncio
from pathlib import Path

from fastmcp import Client

from agent_lab import mcp_server


ROOT = Path(__file__).resolve().parents[1]
TOOL_NAMES = {
    "add", "multiply", "convert_units", "write_note", "read_note",
    "list_notes", "now", "days_between", "search_docs",
}


def test_mcp_tools(monkeypatch, tmp_path: Path) -> None:
    """List every tool and call each one through one MCP client session."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_LAB_NOTES_DIR", str(tmp_path / "notes"))
    monkeypatch.setenv("AGENT_LAB_DOCS_DIR", str(ROOT / "docs_corpus"))

    async def run() -> None:
        """Check tool schemas and results in one session."""
        async with Client(mcp_server.mcp) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools} == TOOL_NAMES
            for tool in tools:
                assert tool.description.strip()
                assert tool.input_schema["type"] == "object"

            assert (await client.call_tool("add", {"a": 2, "b": 3})).data == 5
            assert (await client.call_tool("multiply", {"a": 17, "b": 23})).data == 391
            assert (await client.call_tool("convert_units", {
                "value": 1, "from_unit": "mi", "to_unit": "km",
            })).data == 1.609344
            await client.call_tool("write_note", {"name": "t", "text": "hi"})
            assert (await client.call_tool("read_note", {"name": "t"})).data == "hi"
            assert "t" in (await client.call_tool("list_notes", {})).data
            assert (await client.call_tool("now", {"timezone": "UTC"})).data.endswith("+00:00")
            assert (await client.call_tool("days_between", {
                "start": "2026-10-29", "end": "2026-12-31",
            })).data == 63
            assert (await client.call_tool("search_docs", {"query": "stdio"})).data[0]["file"] == "mcp-basics.md"

    asyncio.run(run())
