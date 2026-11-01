"""Compare the LangGraph loop with the hand-written agent without a model server."""

import json
import socket
from pathlib import Path

import pytest

from agent_lab import fakes, model
import litellm
from agent_lab.agent import LIMIT_MESSAGE
from agent_lab.agent import graph, hand
from agent_lab.mcp_client import McpError, McpTools
from agent_lab.settings import Settings
from agent_lab.trace import Trace


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    """Share a local MCP child across the graph tests."""
    folder = tmp_path_factory.mktemp("graph")
    with McpTools(settings=Settings(notes_dir=str(folder / "notes"),
                                    docs_dir=str(ROOT / "docs_corpus"), timeout_s=30)) as tools:
        yield tools, folder


def _records(path):
    """Read the events from one trace file."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _run_both(script, tools, tmp_path, **kwargs):
    """Run both agents with the same replies and separate traces."""
    hand_fake = fakes.FakeModel(script)
    graph_fake = fakes.FakeChatModel(script)
    with Trace(tmp_path / "hand.jsonl") as hand_trace, Trace(tmp_path / "graph.jsonl") as graph_trace:
        hand_result = hand.run("multiply", model=hand_fake, tools=tools, trace=hand_trace,
                               **{key: value for key, value in kwargs.items() if key != "echo"})
        graph_result = graph.run("multiply", model=graph_fake, tools=tools, trace=graph_trace, **kwargs)
    return (hand_result, _records(hand_trace.path), hand_fake,
            graph_result, _records(graph_trace.path), graph_fake)


def test_two_tool_task_and_trace(session, tmp_path):
    """Match the answer, calls, trace kinds, and echo order for two tools."""
    tools, folder = session
    lines = []
    hand_result, hand_events, _, result, events, fake = _run_both(
        fakes.builtin("two_tool"), tools, tmp_path, echo=lines.append)
    assert result.stopped_by == "answer" and result.steps == 3
    assert result.text == hand_result.text and len(fake.requests) == 3
    calls = lambda records: [(event["name"], json.loads(event["arguments"]))
                             for event in records if event["kind"] == "tool_call"]
    assert calls(events) == calls(hand_events) == [
        ("multiply", {"a": 17, "b": 23}),
        ("write_note", {"name": "result", "text": "17 x 23 = 391"})]
    assert [event["kind"] for event in events] == [event["kind"] for event in hand_events]
    assert (folder / "notes" / "result.md").exists()
    assert lines[0] == "[node: model]"
    assert "[node: tools]" in lines
    assert any(line.startswith("[tool: multiply] 391") for line in lines)
    assert lines[-1] == "[node: model]"


def test_step_limit_matches_hand(session, tmp_path):
    """Run the sixth tool call and record a limit instead of a final answer."""
    tools, _ = session
    script = [{"tool_calls": [{"name": "multiply", "arguments": '{"a": 2, "b": 3}'}]}] * 6
    hand_result, hand_events, _, result, events, fake = _run_both(
        script, tools, tmp_path, max_steps=6)
    assert result == hand_result
    assert result.stopped_by == "limit" and result.text == LIMIT_MESSAGE.format(6)
    assert result.steps == 6 and len(fake.requests) == 6
    assert len([event for event in events if event["kind"] == "tool_result"]) == 6
    assert events[-1]["kind"] == "limit" and not any(
        event["kind"] == "final" for event in events)
    assert [event["kind"] for event in events] == [event["kind"] for event in hand_events]
    with pytest.raises(ValueError):
        graph.run("multiply", model=fake, tools=tools, max_steps=0)


def test_answer_on_last_step(session):
    """Allow a text answer on the sixth model call."""
    tools, _ = session
    script = [{"tool_calls": [{"name": "multiply", "arguments": '{"a": 2, "b": 3}'}]}] * 5
    script.append({"text": "6"})
    result = graph.run("multiply", model=fakes.FakeChatModel(script), tools=tools, max_steps=6)
    assert result.stopped_by == "answer" and result.steps == 6 and result.text == "6"


def test_bad_arguments_match_hand(session, tmp_path):
    """Give the same missing and unknown argument text to both models."""
    tools, _ = session
    script = [{"tool_calls": [{"name": "multiply", "arguments": '{"x": 17, "b": 23}'}]},
              {"text": "done"}]
    _, hand_events, _, _, events, _ = _run_both(script, tools, tmp_path)
    content = lambda records: next(event["content"] for event in records
                                   if event["kind"] == "tool_result")
    assert content(hand_events) == content(events) == (
        "error: missing argument 'a'; unknown argument 'x'")


def test_closed_mcp_error_is_traced(tmp_path):
    """Let an MCP session error leave the graph and enter the trace."""
    tools = McpTools(settings=Settings(notes_dir=str(tmp_path / "notes"),
                                       docs_dir=str(ROOT / "docs_corpus"), timeout_s=30))
    tools.open()
    tools.close()
    script = [{"tool_calls": [{"name": "multiply", "arguments": '{"a": 2, "b": 3}'}]}]
    with Trace(tmp_path / "closed.jsonl") as trace:
        with pytest.raises(McpError):
            graph.run("multiply", model=fakes.FakeChatModel(script), tools=tools, trace=trace)
    assert _records(trace.path)[-1]["kind"] == "error"


def test_unknown_tool_uses_langgraph_text(session, tmp_path):
    """Record ToolNode's unknown tool reply and continue to an answer."""
    tools, _ = session
    script = [{"tool_calls": [{"name": "divide", "arguments": "{}"}]}, {"text": "done"}]
    with Trace(tmp_path / "unknown.jsonl") as trace:
        result = graph.run("divide", model=fakes.FakeChatModel(script), tools=tools, trace=trace)
    event = next(event for event in _records(trace.path) if event["kind"] == "tool_result")
    assert event["content"].startswith("Error: divide is not a valid tool")
    assert event["is_error"] is True and result.stopped_by == "answer"


def test_adapter_lists_and_calls_tools(session):
    """Expose all MCP names and run multiplication through the adapter."""
    tools, _ = session
    adapted = graph.as_langchain_tools(tools)
    assert len(adapted) == 9 and {tool.name for tool in adapted} == set(tools.names())
    multiply = next(tool for tool in adapted if tool.name == "multiply")
    assert float(multiply.invoke({"a": 17, "b": 23})) == 391


def test_chat_model_uses_local_settings():
    """Configure ChatLiteLLM without making a model request."""
    config = Settings(host="localhost", port=8090, model_name="test-model", timeout_s=12)
    model = graph.chat_model(config)
    assert model.model == "openai/test-model"
    assert model.api_base == "http://localhost:8090/v1"
    assert model.request_timeout == 12 and model.max_retries == 0
    assert model.model_kwargs["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": False}}


def test_model_error_is_traced(session, tmp_path):
    """Record an exhausted fake model before raising its error."""
    tools, _ = session
    with Trace(tmp_path / "error.jsonl") as trace:
        with pytest.raises(fakes.ScriptExhausted):
            graph.run("hello", model=fakes.FakeChatModel([]), tools=tools, trace=trace)
    assert _records(trace.path)[-1]["kind"] == "error"


def test_module_has_no_literal_hosts():
    """Keep endpoint hosts out of the graph module source."""
    source = Path(graph.__file__).read_text(encoding="utf-8")
    assert "http://" not in source and "https://" not in source


def test_stopped_model_error_is_traced(session, tmp_path, monkeypatch):
    """Map a graph connection error and save its local address in the trace."""
    tools, _ = session
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    monkeypatch.setenv("AGENT_LAB_HOST", "127.0.0.1")
    monkeypatch.setenv("AGENT_LAB_PORT", str(port))

    class FailingChatModel:
        """Raise the measured LiteLLM connection error during a graph run."""

        def bind_tools(self, _tools):
            """Return this model after the graph offers its tools."""
            return self

        def invoke(self, _messages):
            """Report the local connection failure."""
            raise litellm.InternalServerError("Connection error.", llm_provider="openai", model="m")

    with Trace(tmp_path / "server-down.jsonl") as trace:
        with pytest.raises(model.ModelServerDown):
            graph.run("hello", model=FailingChatModel(), tools=tools, trace=trace)
    error = _records(trace.path)[-1]
    assert error["kind"] == "error"
    assert f"127.0.0.1:{port}" in error["message"]
