"""Check one real local MCP child and its cleanup."""

import json
import time
from pathlib import Path

import pytest
from tests.procs import server_pids

from agent_lab.mcp_client import McpError, McpTools
from agent_lab.settings import Settings


ROOT = Path(__file__).resolve().parents[1]
NAMES = sorted(("add", "multiply", "convert_units", "write_note", "read_note",
                "list_notes", "now", "days_between", "search_docs"))


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    """Open one stdio session and close it after this test module."""
    folder = tmp_path_factory.mktemp("mcp-client")
    client = McpTools(settings=Settings(notes_dir=str(folder / "notes"),
                                        docs_dir=str(ROOT / "docs_corpus"), timeout_s=15))
    with client:
        yield client, folder


def test_tools_and_notes(session):
    """List schemas and run math, errors, and notes through stdio."""
    client, folder = session
    assert len(client.specs()) == 9
    assert client.specs() is client.specs()
    assert client.names() == NAMES
    assert client.schema("multiply")["required"] == ["a", "b"]
    assert client.schema("nope") is None
    text, is_error = client.call("multiply", {"a": 17, "b": 23})
    assert float(text) == 391 and is_error is False
    text, is_error = client.call("convert_units", {"value": 1, "from_unit": "bad", "to_unit": "km"})
    assert is_error is True and "valid units" in text
    text, is_error = client.call("list_notes", {})
    assert json.loads(text) == [] and is_error is False
    text, is_error = client.call("write_note", {"name": "result", "text": "391"})
    assert "saved note 'result'" in text and is_error is False
    assert (folder / "notes" / "result.md").read_text(encoding="utf-8") == "391"
    text, _ = client.call("list_notes", {})
    assert "result" in json.loads(text)


def test_child_cleanup(tmp_path):
    """Prove that closing the wrapper removes its new child process."""
    before = server_pids()
    client = McpTools(settings=Settings(notes_dir=str(tmp_path / "notes"),
                                        docs_dir=str(ROOT / "docs_corpus"), timeout_s=15))
    with client:
        started = server_pids() - before
        assert started
    client.close()
    with pytest.raises(McpError, match="session is closed"):
        client.call("multiply", {"a": 1, "b": 2})
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and started & server_pids():
        time.sleep(0.1)
    assert not started & server_pids()


def test_bad_module_stops(tmp_path):
    """Report startup failure without leaving a server child."""
    before = server_pids()
    client = McpTools(module="agent_lab.no_such_module",
                      settings=Settings(notes_dir=str(tmp_path / "notes"),
                                        docs_dir=str(ROOT / "docs_corpus"), timeout_s=15))
    started = time.monotonic()
    with pytest.raises(McpError, match="^MCP server did not start"):
        client.open()
    assert time.monotonic() - started < 30
    assert not server_pids() - before


def test_interrupt_during_open_stops(tmp_path, monkeypatch):
    """Leave no child or worker thread when startup is interrupted."""
    before = server_pids()
    client = McpTools(settings=Settings(notes_dir=str(tmp_path / "notes"),
                                        docs_dir=str(ROOT / "docs_corpus"), timeout_s=15))

    def interrupt(_timeout):
        """Stand in for Ctrl+C while the caller waits for startup."""
        raise KeyboardInterrupt

    monkeypatch.setattr(client._ready, "wait", interrupt)
    with pytest.raises(KeyboardInterrupt):
        with client:
            pass
    assert not client._thread.is_alive()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and server_pids() - before:
        time.sleep(0.1)
    assert not server_pids() - before
