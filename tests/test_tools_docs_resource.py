"""Check the local docs resource and tool explanation prompt."""

import asyncio
from pathlib import Path

import pytest
from fastmcp import Client

from agent_lab import mcp_server


ROOT = Path(__file__).resolve().parents[1]
TOOL_NAMES = {
    "add", "multiply", "convert_units", "write_note", "read_note",
    "list_notes", "now", "days_between", "search_docs",
}


@pytest.fixture(autouse=True)
def docs_env(monkeypatch):
    """Point the server at the local test docs."""
    monkeypatch.setenv("AGENT_LAB_DOCS_DIR", str(ROOT / "docs_corpus"))


def test_read_doc() -> None:
    """Read the exact text and explain missing or unsafe names."""
    async def run() -> None:
        """Read docs through one local client."""
        async with Client(mcp_server.mcp) as client:
            result = await client.read_resource("docs://mcp-basics")
            assert result[0].text == (ROOT / "docs_corpus" / "mcp-basics.md").read_text(encoding="utf-8")
            for name, message in (("missing", "no doc named 'missing'"),
                                  ("..%2Fx", None), ("CON", "doc names use")):
                with pytest.raises(Exception, match=message):
                    await client.read_resource(f"docs://{name}")

    asyncio.run(run())


def test_resource_listing() -> None:
    """List the template without adding a fixed resource."""
    async def run() -> None:
        """Check both resource lists through one local client."""
        async with Client(mcp_server.mcp) as client:
            assert await client.list_resources() == []
            assert "docs://{name}" in {item.uri_template for item in await client.list_resource_templates()}

    asyncio.run(run())


def test_explain_tool() -> None:
    """Use the server's exact tool description and list valid names on error."""
    async def run() -> None:
        """Check the prompt against the live tool list."""
        async with Client(mcp_server.mcp) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools} == TOOL_NAMES
            description = next(tool.description for tool in tools if tool.name == "multiply")
            prompt = await client.get_prompt("explain_tool", {"tool_name": "multiply"})
            text = prompt.messages[0].content.text
            assert "multiply" in text and description in text
            with pytest.raises(Exception, match="add"):
                await client.get_prompt("explain_tool", {"tool_name": "missing"})

    asyncio.run(run())
