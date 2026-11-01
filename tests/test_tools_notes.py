"""Check that local note tools keep every note inside the selected folder."""

import asyncio
import os
import subprocess
from pathlib import Path

import pytest
from fastmcp import Client

from agent_lab import mcp_server


@pytest.fixture(autouse=True)
def notes_env(monkeypatch, tmp_path):
    """Give each test an empty local folder and isolated settings."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_LAB_NOTES_DIR", str(tmp_path / "notes"))


def call(name: str, arguments: dict | None = None, *, raise_on_error: bool = True):
    """Call one note tool through the in-memory MCP client."""
    async def run():
        async with Client(mcp_server.mcp) as client:
            return await client.call_tool(name, arguments or {}, raise_on_error=raise_on_error)

    return asyncio.run(run())


def error(name: str, arguments: dict) -> str:
    """Return the message from a failed tool call."""
    result = call(name, arguments, raise_on_error=False)
    assert result.is_error
    return result.content[0].text


def test_round_trip(tmp_path) -> None:
    """Keep Unicode and line endings exact, and report updates."""
    for name, text in (("greeting", "Grüße, नमस्ते ✓"), ("lines", "a\r\nb\n")):
        assert call("write_note", {"name": name, "text": text}).data == f"saved note '{name}'"
        assert call("read_note", {"name": name}).data == text
    assert call("list_notes").data == ["greeting", "lines"]
    assert call("write_note", {"name": "greeting", "text": "again"}).data == "updated note 'greeting'"
    assert (tmp_path / "notes" / "greeting.md").read_text(encoding="utf-8") == "again"


def test_relative_folder(monkeypatch, tmp_path) -> None:
    """Resolve a relative notes folder from the current folder."""
    monkeypatch.setenv("AGENT_LAB_NOTES_DIR", "notes_rel")
    assert call("write_note", {"name": "n", "text": "hi"}).data == "saved note 'n'"
    assert (tmp_path / "notes_rel" / "n.md").read_text(encoding="utf-8") == "hi"


def test_bad_names_leave_no_trace(tmp_path) -> None:
    """Reject invalid and device names before any file changes."""
    bad_names = ("../x", "a/b", "C:x", "con", "Com1", "LPT9", "NUL", "aux", "COM9", "", "a" * 65)
    for present in (False, True):
        if present:
            notes = tmp_path / "notes"
            notes.mkdir()
            (notes / "keep.md").write_text("keep", encoding="utf-8")
        before = sorted((str(path.relative_to(tmp_path)), path.stat().st_size if path.is_file() else None)
                        for path in tmp_path.rglob("*"))
        for name in bad_names:
            assert "note names use" in error("write_note", {"name": name, "text": "x"})
            assert "note names use" in error("read_note", {"name": name})
        after = sorted((str(path.relative_to(tmp_path)), path.stat().st_size if path.is_file() else None)
                       for path in tmp_path.rglob("*"))
        assert after == before


def test_length() -> None:
    """Accept the limit and reject one more code point."""
    assert call("write_note", {"name": "limit", "text": "x" * 10000}).data == "saved note 'limit'"
    assert "10000" in error("write_note", {"name": "too_long", "text": "x" * 10001})


def test_junction_escape(tmp_path) -> None:
    """Refuse a note path that resolves through a Windows junction."""
    notes = tmp_path / "notes"
    outside = tmp_path / "outside"
    notes.mkdir()
    outside.mkdir()
    (outside / "keep.txt").write_text("secret", encoding="utf-8")
    junction = notes / "x.md"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
                   check=True, capture_output=True)
    try:
        assert "note path is outside the notes folder" in error("write_note", {"name": "x", "text": "hi"})
        assert "note path is outside the notes folder" in error("read_note", {"name": "x"})
        assert "x" not in call("list_notes").data
        assert [path.name for path in outside.iterdir()] == ["keep.txt"]
        assert (outside / "keep.txt").read_text(encoding="utf-8") == "secret"
    finally:
        os.rmdir(junction)


def test_hard_link(tmp_path) -> None:
    """Refuse writes through a hard link to an outside file."""
    notes = tmp_path / "notes"
    outside = tmp_path / "outside"
    notes.mkdir()
    outside.mkdir()
    target = outside / "target.md"
    target.write_text("original", encoding="utf-8")
    os.link(target, notes / "h.md")
    assert "linked" in error("write_note", {"name": "h", "text": "x"})
    assert target.read_text(encoding="utf-8") == "original"


def test_folder_named_note(tmp_path) -> None:
    """Exclude a folder with an md suffix and explain the read failure."""
    (tmp_path / "notes" / "d.md").mkdir(parents=True)
    assert "d" not in call("list_notes").data
    assert "cannot read note" in error("read_note", {"name": "d"})


def test_missing(tmp_path) -> None:
    """Leave a missing notes folder untouched and explain missing names."""
    assert call("list_notes").data == []
    assert not (tmp_path / "notes").exists()
    assert "list_notes" in error("read_note", {"name": "absent"})
    assert not (tmp_path / "notes").exists()


def test_tool_names() -> None:
    """Expose all three note tools through MCP."""
    async def run():
        async with Client(mcp_server.mcp) as client:
            return {tool.name for tool in await client.list_tools()}

    assert {"write_note", "read_note", "list_notes"} <= asyncio.run(run())


def test_source_is_local() -> None:
    """Keep network addresses out of the server source."""
    source = Path(mcp_server.__file__).read_text(encoding="utf-8")
    assert "http://" not in source and "https://" not in source
