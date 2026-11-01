"""Offer one teaching resource from the local MCP server for lesson tests."""

from pathlib import Path

from agent_lab.mcp_server import mcp


ROOT = Path(__file__).resolve().parents[1]


@mcp.resource("docs://mcp-basics")
def mcp_basics() -> str:
    """Read the MCP teaching document when a client requests it."""
    return (ROOT / "docs_corpus" / "mcp-basics.md").read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run(show_banner=False)
