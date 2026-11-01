"""Check local model requests and reply errors without a server."""

from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from agent_lab import model, model_server, settings
import litellm

S = settings.Settings(host="127.0.0.1", port=9999, model_name="m", timeout_s=7)


def response(content="ok", calls=None, usage=None):
    message = NS(content=content, tool_calls=calls)
    return NS(choices=[NS(message=message)], usage=usage)


def test_request_and_thinking(monkeypatch):
    seen = []
    monkeypatch.setattr(litellm, "completion", lambda **kw: (seen.append(kw), response())[1])
    messages = [{"role": "system", "content": "help"}, {"role": "user", "content": [1]}]
    original = deepcopy(messages)
    model.chat(messages, settings=S)
    assert messages == original
    assert seen[-1] == {"model": "openai/m", "api_base": "http://127.0.0.1:9999/v1",
                        "api_key": "local", "timeout": 7, "max_retries": 0, "messages": messages,
                        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
    assert seen[-1]["messages"] is not messages
    model.chat(messages, tools=[{"x": 1}], response_format={"type": "json_object"}, settings=S)
    assert seen[-1]["tools"] == [{"x": 1}]
    assert seen[-1]["response_format"] == {"type": "json_object"}
    assert "num_retries" not in seen[-1]
    model.chat([{"role": "system", "content": []}], settings=S)
    assert seen[-1]["messages"] == [{"role": "system", "content": []}]
    model.chat(messages, thinking=True, settings=S)
    assert seen[-1]["messages"] == messages
    assert "extra_body" not in seen[-1]


def test_reply_mapping(monkeypatch):
    calls = [NS(id="a", function=NS(name="one", arguments='{"x":1}')),
             NS(id="b", function=NS(name="two", arguments='{"y":2}'))]
    monkeypatch.setattr(litellm, "completion", lambda **kw: response(None, calls, NS(prompt_tokens=3,
                        completion_tokens=None, total_tokens=5)))
    reply = model.chat([], settings=S)
    assert reply.text == ""
    assert reply.tool_calls == [model.ToolCall("a", "one", '{"x":1}'),
                                model.ToolCall("b", "two", '{"y":2}')]
    assert reply.usage == {"prompt_tokens": 3, "completion_tokens": 0, "total_tokens": 5}
    monkeypatch.setattr(litellm, "completion", lambda **kw: response("yes", None, None))
    reply = model.chat([], settings=S)
    assert reply.tool_calls == []
    assert reply.usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    monkeypatch.setattr(litellm, "completion", lambda **kw: NS(choices=[], usage=None))
    with pytest.raises(model.ModelError, match="model returned no choices"):
        model.chat([], settings=S)


@pytest.mark.parametrize("error,kind,text", [
    (litellm.Timeout("t", model="m", llm_provider="openai"), model.ModelTimeout,
     "model did not answer within 7 s (timeout_s)"),
    (litellm.APIConnectionError("c", llm_provider="openai", model="m"), model.ModelServerDown,
     "cannot reach the model at 127.0.0.1:9999; run: agent-lab model start"),
    (litellm.BadRequestError("too long", model="m", llm_provider="openai"), model.ModelError,
     "too long"),
])
def test_errors(monkeypatch, error, kind, text):
    def fail(**kwargs):
        raise error
    monkeypatch.setattr(litellm, "completion", fail)
    with pytest.raises(kind) as caught:
        model.chat([], settings=S)
    if kind is model.ModelError:
        assert text in str(caught.value)
    else:
        assert str(caught.value) == text
    assert caught.value.__cause__ is error


def test_host_and_settings(monkeypatch):
    seen = []
    monkeypatch.setattr(litellm, "completion", lambda **kw: (seen.append(kw), response())[1])
    bad = settings.Settings(host="example.com")
    with pytest.raises(model_server.ModelServerError):
        model.chat([], settings=bad)
    assert not seen
    monkeypatch.setattr(settings, "load", lambda: S)
    model.chat([])
    assert seen[-1]["model"] == "openai/m"
    assert not hasattr(litellm, "telemetry")


@pytest.mark.parametrize("port_used,kind", [
    (False, model.ModelServerDown),
    (True, model.ModelError),
])
def test_internal_server_error(monkeypatch, port_used, kind):
    """Explain a stopped server and preserve errors from a running server."""
    error = litellm.InternalServerError("Connection error.", llm_provider="openai", model="m")

    def fail(**kwargs):
        raise error

    monkeypatch.setattr(litellm, "completion", fail)
    monkeypatch.setattr(model_server, "port_in_use", lambda settings: port_used)
    with pytest.raises(kind) as caught:
        model.chat([], settings=S)
    if port_used:
        assert "Connection error." in str(caught.value)
    else:
        assert str(caught.value) == "cannot reach the model at 127.0.0.1:9999; run: agent-lab model start"
    assert caught.value.__cause__ is error


def test_litellm_banner_is_suppressed(monkeypatch):
    """Keep LiteLLM debug messages out of the lesson output."""
    litellm.suppress_debug_info = False
    monkeypatch.setattr(litellm, "completion", lambda **kw: response())
    model.chat([], settings=S)
    assert litellm.suppress_debug_info is True


def test_model_error_ignores_unrelated_errors(monkeypatch):
    """Leave ordinary errors alone without reading settings."""
    monkeypatch.setattr(settings, "load", lambda: pytest.fail("settings were read"))
    assert model.model_error(ValueError("x"), S) is None


def test_model_error_maps_timeout():
    """Include the configured timeout in a mapped model error."""
    error = litellm.Timeout("t", model="m", llm_provider="openai")
    mapped = model.model_error(error, S)
    assert isinstance(mapped, model.ModelTimeout)
    assert str(mapped) == "model did not answer within 7 s (timeout_s)"


def test_model_error_maps_stopped_server(monkeypatch):
    """Name the configured host and port when the server is down."""
    error = litellm.InternalServerError("Connection error.", llm_provider="openai", model="m")
    monkeypatch.setattr(model_server, "port_in_use", lambda settings: False)
    mapped = model.model_error(error, S)
    assert isinstance(mapped, model.ModelServerDown)
    assert "127.0.0.1:9999" in str(mapped)
