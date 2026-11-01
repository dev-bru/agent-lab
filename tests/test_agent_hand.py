"""Check the hand-written loop with scripted replies and real tools."""

import json
from pathlib import Path

import pytest

from agent_lab import fakes, model
from agent_lab.agent import LIMIT_MESSAGE
from agent_lab.agent.hand import run
from agent_lab.mcp_client import McpTools
from agent_lab.settings import Settings
from agent_lab.trace import Trace


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    """Share one real MCP child across the agent tests."""
    folder = tmp_path_factory.mktemp("hand")
    with McpTools(settings=Settings(notes_dir=str(folder / "notes"),
                                    docs_dir=str(ROOT / "docs_corpus"), timeout_s=15)) as tools:
        yield tools, folder


def _records(path):
    """Read the events written by one trace."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_two_tool_task_and_echo(session, tmp_path):
    """Multiply, save the answer, and echo each step and tool result."""
    tools, folder = session
    fake = fakes.FakeModel(fakes.builtin("two_tool"))
    lines = []
    with Trace(tmp_path / "run.jsonl") as trace:
        result = run("Multiply 17 by 23 and save the answer as result.", model=fake,
                     tools=tools, trace=trace, echo=lines.append)
    assert result.stopped_by == "answer" and result.steps == 3 and "391" in result.text
    assert len(fake.requests) == 3
    calls = [event for event in _records(trace.path) if event["kind"] == "tool_call"]
    assert [(call["name"], json.loads(call["arguments"])) for call in calls] == [
        ("multiply", {"a": 17, "b": 23}),
        ("write_note", {"name": "result", "text": "17 x 23 = 391"})]
    assert (folder / "notes" / "result.md").exists()
    assert "[step 1/6]" in lines
    assert any(line.startswith("[tool: multiply] 391") for line in lines)
    assert "[tool: write_note] saved note 'result'" in lines


def test_bad_arguments_reach_model(session):
    """Give missing and unknown arguments back to the model for repair."""
    tools, _ = session
    fake = fakes.FakeModel([
        {"tool_calls": [{"name": "multiply", "arguments": '{"x": 17, "b": 23}'}]},
        {"tool_calls": [{"name": "multiply", "arguments": '{"a": 17, "b": 23}'}]},
        {"text": "391"}])
    result = run("multiply", model=fake, tools=tools)
    assert result.stopped_by == "answer"
    message = fake.requests[1]["messages"][-1]["content"]
    assert "unknown argument 'x'" in message and "missing argument 'a'" in message


class Stub:
    """Return fixed replies, including arguments the script loader rejects."""

    def __init__(self, *replies):
        """Keep the replies in their model call order."""
        self.replies = iter(replies)
        self.requests = []

    def chat(self, messages, tools=None):
        """Record the conversation and return the next reply."""
        self.requests.append(list(messages))
        return next(self.replies)


def _reply(name, arguments):
    """Make a tool request with a stable call id."""
    return model.Reply("", [model.ToolCall("one", name, arguments)], {})


def test_invalid_json_and_blank_arguments(session, tmp_path):
    """Reject bad JSON and treat a blank no-argument call as empty JSON."""
    tools, _ = session
    bad = Stub(_reply("multiply", "{bad"), model.Reply("ok", [], {}))
    assert run("bad", model=bad, tools=tools).stopped_by == "answer"
    assert bad.requests[1][-1]["content"] == "error: arguments are not valid JSON"
    blank = Stub(_reply("list_notes", ""), model.Reply("ok", [], {}))
    with Trace(tmp_path / "blank.jsonl") as trace:
        assert run("list", model=blank, tools=tools, trace=trace).stopped_by == "answer"
    results = [event for event in _records(trace.path) if event["kind"] == "tool_result"]
    assert results[0]["is_error"] is False


def test_none_arguments_reach_model(session):
    """Give a bad non-string argument to the model as a tool error."""
    tools, _ = session
    fake = Stub(_reply("multiply", None), model.Reply("ok", [], {}))
    assert run("bad", model=fake, tools=tools).stopped_by == "answer"
    assert fake.requests[1][-1]["content"] == "error: arguments are not valid JSON"


def test_unknown_tool(session):
    """Tell the model which tools it can use."""
    tools, _ = session
    fake = fakes.FakeModel([{"tool_calls": [{"name": "divide", "arguments": "{}"}]},
                            {"text": "ok"}])
    assert run("divide", model=fake, tools=tools).stopped_by == "answer"
    message = fake.requests[1]["messages"][-1]["content"]
    assert "unknown tool 'divide'; valid tools:" in message
    assert all(name in message for name in tools.names())


def test_step_limit(session, tmp_path):
    """Run the final allowed tool before recording the limit."""
    tools, _ = session
    script = [{"tool_calls": [{"name": "multiply", "arguments": '{"a": 17, "b": 23}'}]}] * 6
    fake = fakes.FakeModel(script)
    with Trace(tmp_path / "limit.jsonl") as trace:
        result = run("multiply", model=fake, tools=tools, trace=trace, max_steps=6)
    records = _records(trace.path)
    assert result.stopped_by == "limit" and result.text == LIMIT_MESSAGE.format(6)
    assert result.steps == 6 and len(fake.requests) == 6
    assert len([event for event in records if event["kind"] == "tool_result"]) == 6
    assert records[-1]["kind"] == "limit" and records[-1]["steps"] == 6
    assert not any(event["kind"] == "final" for event in records)
    short = fakes.FakeModel(script)
    assert run("multiply", model=short, tools=tools, max_steps=2).steps == 2
    assert len(short.requests) == 2
    with pytest.raises(ValueError):
        run("multiply", model=fake, tools=tools, max_steps=0)


def test_model_error_is_traced(session, tmp_path):
    """Record a model failure and let the caller handle it."""
    tools, _ = session

    class Down:
        """Stand in for an unavailable local model."""

        def chat(self, messages, tools=None):
            """Raise the model's server error."""
            raise model.ModelServerDown("down")

    with Trace(tmp_path / "error.jsonl") as trace:
        with pytest.raises(model.ModelServerDown, match="down"):
            run("hello", model=Down(), tools=tools, trace=trace)
    assert _records(trace.path)[-1]["kind"] == "error"
