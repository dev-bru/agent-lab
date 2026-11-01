"""Replay fixed model answers without a server."""

import json
from copy import deepcopy
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, PrivateAttr

from agent_lab.model import Reply, ToolCall


class ScriptExhausted(RuntimeError):
    """Report that a fake has no answer left."""


def builtin(name: str) -> Path:
    """Find a script included with Agent Lab."""
    return Path(__file__).parent / "fake_scripts" / f"{name}.json"


def load_script(source: list | Path | str) -> list:
    """Read and check each scripted answer."""
    path = None
    if isinstance(source, (Path, str)):
        path = Path(source)
        try:
            source = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid script path {path}: {error}") from error
    if not isinstance(source, list):
        raise ValueError(f"reply 0: script must be a list{f' in {path}' if path else ''}")
    script = deepcopy(source)
    for index, reply in enumerate(script):
        if not isinstance(reply, dict) or set(reply) not in ({"text"}, {"tool_calls"}):
            raise ValueError(f"reply {index}: use exactly one reply kind")
        if "text" in reply:
            if not isinstance(reply["text"], str):
                raise ValueError(f"reply {index}: text must be a string")
            continue
        calls = reply["tool_calls"]
        if not isinstance(calls, list) or not calls:
            raise ValueError(f"reply {index}: tool_calls must be a nonempty list")
        for call in calls:
            if (not isinstance(call, dict) or set(call) != {"name", "arguments"}
                    or not isinstance(call["name"], str)
                    or not isinstance(call["arguments"], str)):
                raise ValueError(f"reply {index}: invalid tool call")
            try:
                json.loads(call["arguments"])
            except json.JSONDecodeError as error:
                raise ValueError(f"reply {index}: invalid arguments JSON") from error
    return script


class FakeModel:
    """Return scripted replies through the small chat interface."""

    def __init__(self, script):
        """Check the script and start at its first reply."""
        self.script = load_script(script)
        self.requests = []
        self._index = 0
        self._calls = 0

    def chat(self, messages, tools=None, response_format=None, thinking=False, *, settings=None) -> Reply:
        """Record a request and return the next reply."""
        self.requests.append({"messages": deepcopy(messages), "tools": tools,
                              "response_format": response_format, "thinking": thinking})
        if self._index >= len(self.script):
            raise ScriptExhausted("script has no replies left")
        reply = self.script[self._index]
        self._index += 1
        calls = []
        for call in reply.get("tool_calls", []):
            self._calls += 1
            calls.append(ToolCall(f"call_{self._calls}", call["name"], call["arguments"]))
        return Reply(reply.get("text", ""), calls,
                     {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})


class FakeChatModel(BaseChatModel):
    """Return scripted answers through LangChain's chat interface."""

    script: list
    requests: list = Field(default_factory=list)
    bound_tools: list = Field(default_factory=list)
    _index: int = PrivateAttr(0)
    _calls: int = PrivateAttr(0)

    def __init__(self, script, **kwargs):
        """Check the script and prepare the chat model."""
        super().__init__(script=load_script(script), **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        """Record messages and make the next chat answer."""
        self.requests.append(deepcopy(list(messages)))
        if self._index >= len(self.script):
            raise ScriptExhausted("script has no replies left")
        reply = self.script[self._index]
        self._index += 1
        calls = []
        for call in reply.get("tool_calls", []):
            self._calls += 1
            calls.append({"name": call["name"], "args": json.loads(call["arguments"]),
                          "id": f"call_{self._calls}", "type": "tool_call"})
        return ChatResult(generations=[ChatGeneration(
            message=AIMessage(content=reply.get("text", ""), tool_calls=calls))])

    def bind_tools(self, tools, **kwargs):
        """Save the offered tools and return this model."""
        self.bound_tools = list(tools)
        return self

    @property
    def _llm_type(self) -> str:
        """Name this fake for LangChain."""
        return "agent-lab-fake"
