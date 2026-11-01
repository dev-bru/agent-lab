"""Send chat messages to the local model."""

import os
import sys
from copy import deepcopy
from dataclasses import dataclass
from urllib.parse import urlunsplit

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
for _key in ("NO_PROXY", "no_proxy"):
    _entries = [entry for entry in os.environ.get(_key, "").split(",") if entry]
    for _host in ("127.0.0.1", "localhost"):
        if _host not in _entries:
            _entries.append(_host)
    os.environ[_key] = ",".join(_entries)

from agent_lab import model_server, settings as settings_module


@dataclass(frozen=True)
class ToolCall:
    """Store one tool request from the model."""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Reply:
    """Store the model answer and token counts."""

    text: str
    tool_calls: list[ToolCall]
    usage: dict


class ModelError(RuntimeError):
    """Report a model reply or request error."""


class ModelServerDown(ModelError):
    """Report that the local model cannot be reached."""


class ModelTimeout(ModelError):
    """Report that the local model took too long."""


def server_down(settings) -> ModelServerDown:
    """Explain how to start the local model server."""
    return ModelServerDown(
        f"cannot reach the model at {settings.host}:{settings.port}; run: agent-lab model start"
    )


def model_error(error, settings=None) -> ModelError | None:
    """Turn known LiteLLM failures into local model errors."""
    if "litellm" not in sys.modules:
        return None
    import litellm

    if isinstance(error, litellm.Timeout):
        if settings is None:
            settings = settings_module.load()
        return ModelTimeout(f"model did not answer within {settings.timeout_s} s (timeout_s)")
    if isinstance(error, (litellm.APIConnectionError, litellm.InternalServerError)):
        if settings is None:
            settings = settings_module.load()
        if isinstance(error, litellm.APIConnectionError) or not model_server.port_in_use(settings):
            return server_down(settings)
        return ModelError(str(error))
    if isinstance(error, litellm.BadRequestError):
        return ModelError(str(error))
    return None


def chat(messages, tools=None, response_format=None, thinking=False, *, settings=None) -> Reply:
    """Ask the local model for one reply."""
    import litellm
    # LiteLLM loads here because it is slow to import and fake runs do not need it.
    litellm.suppress_debug_info = True
    if settings is None:
        settings = settings_module.load()
    model_server.check_host(settings)
    prepared = deepcopy(messages)
    kwargs = {
        "model": f"openai/{settings.model_name}",
        "api_base": urlunsplit(("http", f"{settings.host}:{settings.port}", "/v1", "", "")),
        "api_key": "local",
        "timeout": settings.timeout_s,
        # The local server is up or down; retries only make the user wait, as in the graph engine.
        "max_retries": 0,
        "messages": prepared,
    }
    if not thinking:
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    if tools is not None:
        kwargs["tools"] = tools
    if response_format is not None:
        kwargs["response_format"] = response_format
    try:
        response = litellm.completion(**kwargs)
    except Exception as error:
        mapped = model_error(error, settings)
        if mapped is not None:
            raise mapped from error
        raise
    if not response.choices:
        raise ModelError("model returned no choices")
    message = response.choices[0].message
    calls = [ToolCall(tc.id, tc.function.name, tc.function.arguments)
             for tc in (message.tool_calls or [])]
    usage = response.usage
    counts = {key: (getattr(usage, key, None) or 0)
              for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    return Reply(message.content or "", calls, counts)
