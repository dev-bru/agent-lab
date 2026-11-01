"""Check ordered trace lines and unique run names."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agent_lab import fakes, trace as trace_module
from agent_lab.agent.hand import run
from agent_lab.mcp_client import McpTools
from agent_lab.settings import Settings
from agent_lab.trace import Trace


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    """Keep one stdio child open for this test module."""
    folder = tmp_path_factory.mktemp("trace")
    with McpTools(settings=Settings(notes_dir=str(folder / "notes"),
                                    docs_dir=str(ROOT / "docs_corpus"), timeout_s=15)) as tools:
        yield tools


def test_run_trace(session, tmp_path):
    """Write the two-tool journey in time order, then read it after close."""
    with Trace.new(tmp_path / "runs", "hand") as trace:
        run("Multiply 17 and 23 and save result.", model=fakes.FakeModel(fakes.builtin("two_tool")),
            tools=session, trace=trace)
    records = [json.loads(line) for line in trace.path.read_text(encoding="utf-8").splitlines()]
    assert re.fullmatch(r"\d{8}T\d{6}_\d{3}-hand\.jsonl", trace.path.name)
    assert all("t" in record and "kind" in record for record in records)
    assert [record["t"] for record in records] == sorted(record["t"] for record in records)
    assert [record["kind"] for record in records] == [
        "user", "model_request", "model_reply", "tool_call", "tool_result",
        "model_request", "model_reply", "tool_call", "tool_result",
        "model_request", "model_reply", "final"]


def test_name_collision_and_validation(monkeypatch, tmp_path):
    """Add a number when two runs start in the same millisecond."""
    fixed = datetime(2026, 10, 30, 12, 34, 56, 123000, tzinfo=timezone.utc)

    class FixedDateTime:
        """Return one fixed UTC time for file names."""

        @staticmethod
        def now(tz):
            """Give the requested timezone its fixed timestamp."""
            return fixed.astimezone(tz)

    monkeypatch.setattr(trace_module, "datetime", FixedDateTime)
    with Trace.new(tmp_path, "hand") as first, Trace.new(tmp_path, "hand") as second:
        assert first.path != second.path
        assert second.path.name.endswith("-2.jsonl")
    with pytest.raises(ValueError):
        Trace.new(tmp_path, "Hand!")
    with Trace(tmp_path / "bad.jsonl") as trace:
        with pytest.raises(ValueError):
            trace.write("unknown")
        trace.write("user", text="café")
    assert "café" in trace.path.read_text(encoding="utf-8")


def test_lone_surrogate_is_written(tmp_path):
    """Write an invalid Unicode character as its readable escape."""
    with Trace(tmp_path / "surrogate.jsonl") as trace:
        trace.write("final", text="hi \ud800")
    assert "\\ud800" in trace.path.read_text(encoding="utf-8")
