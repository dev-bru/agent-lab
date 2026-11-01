# Agent Lab: architecture

Status: draft (2026-10-29), plan stage 3. Nothing is built yet. The interactive version is
`plan/03-architecture.html` (open it in a browser; keys 1-6 pick a flow, arrows step, O switches the mode).
Code shapes below are the plan; the build confirms them. Labels: MEASURED (on this PC), UNVERIFIED (not yet checked).

## Components
| Node | What it is | Where |
|---|---|---|
| Learner | Terminal chat (`app/chat.py`) or one lesson script | this PC |
| Agent loop | By hand: a plain Python `for` loop (`agent/hand.py`). LangGraph: a `StateGraph` (`agent/graph.py`) | in-process |
| Pydantic schema | Builds JSON schemas and checks model output (lesson 03) | in-process |
| LiteLLM | One API for every model provider. By hand: `litellm.completion()`. LangGraph: `ChatLiteLLM` | pip, pinned |
| Qwen3 1.7B | `llama-server` (llama.cpp CUDA build 11408), `--jinja -ngl 99 -c 8192` | `127.0.0.1:8090/v1` |
| MCP tool server | FastMCP server, started by the agent as a child process | stdio, no port |
| Sandbox + docs | `sandbox/notes/` (the only folder tools may write) and `docs/*.md` (read-only) | local files |
| Run trace | `runs/<id>.jsonl`, one JSON line per event; `viewer.html` replays it | local files |

## Modes
- **By hand (LiteLLM loop):** every moving part is visible code: the loop, tool dispatch, argument checks, step limit.
- **LangGraph (framework):** the same agent. LangGraph owns the loop (`model` node, `tools` node, one conditional
  edge). a small adapter of our own (D-012) turns the same MCP tools into LangChain tools; `ChatLiteLLM` keeps LiteLLM underneath. The model,
  tools and trace format do not change, so the two agents compare line for line.

## Flows
1. **Model call (lesson 01).** Learner -> agent -> LiteLLM -> `POST /v1/chat/completions` -> answer back.
   `model="openai/qwen3-1.7b"`, `api_base="http://127.0.0.1:8090/v1"`, placeholder `api_key`. `/no_think` in the
   system message turns off Qwen3 thinking (MEASURED: gives a direct answer).
2. **Tool call (lesson 02).** The request carries a tool list (name, description, JSON schema). The model replies
   with `tool_calls` instead of text (MEASURED: `multiply {"a":17,"b":23}` in 1.26 s). The agent checks the
   arguments, runs the tool, adds a `role: tool` message with the same call id, and calls the model again for the
   final answer. The model never runs code; it only asks.
3. **Structured output (lesson 03).** A Pydantic model -> JSON schema -> `response_format`. The reply is text until
   `model_validate_json()` passes. On failure the exact error goes back to the model once; a second failure is shown
   and the agent stops. UNVERIFIED: that llama-server enforces the schema with a grammar on this build.
4. **Agent loop (lesson 04).** Repeat: ask the model, run what it asks, add the result. Stop on an answer without a
   tool call or at `MAX_STEPS` (6). Bad tool arguments do not crash the loop: the error goes back as the tool result
   so the model can repair the call. The notes tool writes only inside `sandbox/notes` (rejects `..`, slashes,
   drive letters). Every event goes to the run trace.
5. **MCP over stdio (lesson 05).** The agent spawns the server with the venv Python, then JSON-RPC 2.0 over
   stdin/stdout: `initialize` -> capabilities -> `tools/list` (schemas built from type hints) -> `tools/call` /
   `resources/read`. Closing the client ends the child process.
6. **LangGraph graph (lesson 06, LangGraph mode only).** `START -> model -> (tool call? tools : END)`,
   `tools -> model`. `ToolNode` turns tool errors into `ToolMessage`s, like the hand loop. `graph.stream()` writes
   the same trace format.

## Proposed tool catalog (final list in REQUIREMENTS.md)
| Group | Tools / resources |
|---|---|
| Math and units | `add`, `multiply`, `convert_units` |
| Notes (sandbox) | `write_note`, `read_note`, `list_notes` |
| Date and time | `now`, `days_between` |
| Docs | `search_docs`, resource `docs://{name}`, one prompt |

## Workshop scenarios (things to try)
- Ask "17 times 23" with and without the tool list; compare the answers.
- Break a tool argument on purpose (fake model) and watch the loop repair it in the trace viewer.
- Set `MAX_STEPS = 1` and see the step-limit message.
- Run lesson 04 and lesson 06 on the same question; diff the two traces.
- Stop `llama-server` and see the clear "model server not running" error.

## Boundaries
No cloud models or API keys, no internet tools, no web chat, no vector database (ASSUMPTION, confirm at the SPEC
GATE). One GPU model at a time; stop `llama-server` when idle.
