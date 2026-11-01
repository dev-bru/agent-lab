"""Check local docs search through an in-memory MCP client."""

import asyncio
import re
from pathlib import Path

import pytest
from fastmcp import Client

from agent_lab import mcp_server

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def docs_env(monkeypatch, tmp_path):
    """Give each test an isolated working folder and docs setting."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_LAB_DOCS_DIR", str(tmp_path / "docs"))


def call(query: str, limit: int = 3, *, raise_on_error: bool = True):
    """Call docs search through the local MCP client."""
    async def run():
        async with Client(mcp_server.mcp) as client:
            return await client.call_tool("search_docs", {"query": query, "limit": limit},
                                          raise_on_error=raise_on_error)

    return asyncio.run(run())


def put(tmp_path: Path, name: str, text: str) -> None:
    """Write one test document into the selected docs folder."""
    folder = tmp_path / "docs"
    folder.mkdir(exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8", newline="")


def error(query: str, limit: int = 3) -> str:
    """Return the text of a failed docs search."""
    result = call(query, limit, raise_on_error=False)
    assert result.is_error
    return result.content[0].text


def test_ranking(tmp_path) -> None:
    """Rank by all hits and report the first best line."""
    put(tmp_path, "alpha.md", "the junction here\n")
    put(tmp_path, "beta.md", "other\nmore\njunction and junction\n")
    put(tmp_path, "gamma.md", "no match\n")
    assert call("junction").data == [
        {"file": "beta.md", "line": 3, "text": "junction and junction"},
        {"file": "alpha.md", "line": 1, "text": "the junction here"},
    ]
    assert isinstance(call("junction").data[0]["line"], int)
    assert call("absent").data == []


def test_tie_and_limit(tmp_path) -> None:
    """Break score ties by file name and apply the result limit."""
    put(tmp_path, "b.md", "tie")
    put(tmp_path, "a.md", "tie")
    assert call("tie").data == [
        {"file": "a.md", "line": 1, "text": "tie"},
        {"file": "b.md", "line": 1, "text": "tie"},
    ]
    assert call("tie", 1).data == [{"file": "a.md", "line": 1, "text": "tie"}]


def test_case_and_whole_words(tmp_path) -> None:
    """Match letter case freely but require complete words."""
    put(tmp_path, "upper.md", "Junction JUNCTION")
    put(tmp_path, "suffix.md", "junctions junctionx")
    assert call("junction").data == [{"file": "upper.md", "line": 1, "text": "Junction JUNCTION"}]
    assert call("JUNCTION junction").data == [{"file": "upper.md", "line": 1, "text": "Junction JUNCTION"}]
    (tmp_path / "docs" / "upper.md").unlink()
    assert call("junction").data == []


def test_crlf_and_best_line(tmp_path) -> None:
    """Preserve line numbers and remove the carriage return from results."""
    put(tmp_path, "crlf.md", "other\r\njunction\r\nmore\r\njunction\r\n")
    assert call("junction").data == [{"file": "crlf.md", "line": 2, "text": "junction"}]


def test_ignored_entries(tmp_path) -> None:
    """Search direct files and ignore folders with a markdown suffix."""
    (tmp_path / "docs" / "sub").mkdir(parents=True)
    (tmp_path / "docs" / "sub" / "x.md").write_text("junction", encoding="utf-8")
    (tmp_path / "docs" / "d.md").mkdir()
    assert call("junction").data == []


def test_missing_or_file_folder(monkeypatch, tmp_path) -> None:
    """Return no matches when the docs path is absent or a file."""
    assert call("junction").data == []
    file = tmp_path / "docs"
    file.write_text("junction", encoding="utf-8")
    monkeypatch.setenv("AGENT_LAB_DOCS_DIR", str(file))
    assert call("junction").data == []


def test_errors_and_truncation(tmp_path) -> None:
    """Check query first, enforce limits, and shorten long result lines."""
    for query in ("", "   ", "!!!"):
        assert "at least one word" in error(query)
    assert "at least one word" in error("", 0)
    for limit in (0, 11):
        assert "1 to 10" in error("word", limit)
    put(tmp_path, "long.md", "junction " + "x" * 391)
    assert call("junction").data == [{"file": "long.md", "line": 1,
                                       "text": ("junction " + "x" * 391)[:300]}]


def test_shipped_corpus(monkeypatch) -> None:
    """Find each distinctive term in its own shipped document."""
    monkeypatch.setenv("AGENT_LAB_DOCS_DIR", str(ROOT / "docs_corpus"))
    for word, name in (("stdio", "mcp-basics.md"), ("role", "tool-calling.md"),
                       ("trace", "agent-loop.md")):
        result = call(word).data
        assert result and result[0]["file"] == name
        assert isinstance(result[0]["line"], int)


def test_corpus_structure() -> None:
    """Keep the three teaching documents short and easy to read."""
    required = {
        "mcp-basics.md": {"stdio", "schemas", "isError"},
        "tool-calling.md": {"tool_calls", "tool_call_id", "role"},
        "agent-loop.md": {"max_steps", "trace"},
    }
    for name, words in required.items():
        source = (ROOT / "docs_corpus" / name).read_bytes().decode("utf-8")
        lines = source.splitlines()
        assert 15 <= len(lines) <= 30
        assert lines[0].startswith("# ")
        assert "\r" not in source and "http" not in source.lower()
        assert words <= set(re.findall(r"[A-Za-z0-9_]+", source))
        assert all(len(sentence.split()) <= 20 for sentence in re.split(r"[.!?](?:\s+|$)", source))
    for word, owner in (("stdio", "mcp-basics.md"), ("role", "tool-calling.md"),
                        ("trace", "agent-loop.md")):
        for name in required:
            source = (ROOT / "docs_corpus" / name).read_text(encoding="utf-8")
            assert bool(re.search(rf"\b{word}\b", source, re.IGNORECASE)) == (name == owner)


def test_tool_name() -> None:
    """Expose docs search through MCP."""
    async def run():
        async with Client(mcp_server.mcp) as client:
            return {tool.name for tool in await client.list_tools()}

    assert "search_docs" in asyncio.run(run())


def test_source_is_local() -> None:
    """Keep network addresses out of the server source."""
    source = (ROOT / "src" / "agent_lab" / "mcp_server.py").read_text(encoding="utf-8")
    assert "http://" not in source and "https://" not in source
