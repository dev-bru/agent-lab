# Agent Lab: architecture

Status: draft for the SPEC GATE (2026-10-29), revised after spec audit 1. REQUIREMENTS.md wins on any detail. Interactive version: `plan/03-architecture.html` (six flows, two
modes). Flow walkthrough: `plan/03-architecture.md`.

## Stack
| Part | Chosen | Rejected (why) |
|---|---|---|
| Language | Python 3.12 via uv | none considered (harness default) |
| Model runtime | llama.cpp `llama-server` build 11408 (CUDA), already on this PC; MEASURED tool calls | Ollama (not installed; one more install) |
| Model | Qwen3 1.7B Q8_0 GGUF, 1.83 GB, Apache-2.0, SHA-256 verified | larger models (4 GB GPU) |
| Model API | LiteLLM 1.106.6 (one API for every provider) | raw `openai` client (teaches one provider only) |
| Framework | LangGraph 1.2.18 + langchain-litellm 0.11.2 | OpenAI Agents SDK (less common for graph agents) |
| Tool protocol | MCP via FastMCP 4.1.4, stdio | HTTP transport (needs a port; nothing gained locally) |
| MCP to LangGraph | own small adapter in `agent/graph.py` (D-012) | langchain-mcp-adapters 0.3.2 (needs mcp<2; FastMCP 4.1.4 needs mcp>=2.3: MEASURED conflict) |
| Validation | Pydantic (comes with FastMCP/LiteLLM; version from the lock) | jsonschema package (one more dependency) |
| Time zones | `zoneinfo` + `tzdata` package (Windows has no system tz database) | fixed UTC offsets (wrong across DST) |
| Tests | pytest + scripted fake model; Python Playwright for the viewer, using installed Chrome (UNVERIFIED: Chrome channel works with the pinned version) | real model in every test (slow, flaky) |

Versions: DOCUMENTED from PyPI on 2026-10-29 (`plan/02-research.md`). Exact pins and hashes live in `uv.lock`.
pytest, playwright and tzdata versions are chosen at setup and logged in `docs/DEPENDENCIES.md`.

## Layout
```
agent-lab/
  pyproject.toml  uv.lock  agent-lab.example.toml  README.md
  src/agent_lab/
    settings.py      # REQ-002: toml + env overrides
    model_server.py  # REQ-003: start/stop/status llama-server
    model.py         # REQ-004/005: chat() on LiteLLM, errors, no-network env
    fakes.py         # FakeModel, FakeChatModel (used by tests, lessons, --fake)
    fake_scripts/    # JSON reply scripts, incl. two_tool.json (canonical task)
    mcp_client.py    # McpTools: open stdio session, specs(), call()
    tools_schema.py  # MCP tool -> OpenAI tool format, argument checks
    mcp_server.py    # REQ-020..023: FastMCP server (python -m agent_lab.mcp_server)
    trace.py         # REQ-041: JSON-lines trace writer
    agent/__init__.py  # RunResult, LIMIT_MESSAGE
    agent/hand.py    # REQ-030
    agent/graph.py   # REQ-031
    cli.py           # REQ-040: agent-lab chat | model
  lessons/01_model_call.py ... 06_langgraph_agent.py
  viewer/viewer.html # REQ-042
  docs/ (this file, specs, DEPENDENCIES.md, exec-plans/), docs_corpus/*.md (searched by search_docs)
  sandbox/notes/     # notes_dir: the only folder tools write (gitignored)
  runs/              # runs_dir: traces (gitignored)
  .agent-lab/        # model.pid, model.log (gitignored)
  tests/conftest.py (socket guard)  tests/test_*.py  tests/live/test_*.py
  plan/              # intake artifacts, including 03-architecture.html
```

## Components and contracts
- **Settings** (`settings.py`): frozen dataclass; load order: defaults < `agent-lab.toml` < env `AGENT_LAB_*`.
- **Model** (`model.py`): `chat(messages, tools=None, response_format=None, thinking=False) -> Reply` where
  `Reply` has `text`, `tool_calls: list[ToolCall(id, name, arguments: str)]`, `usage`. `FakeModel` has the same
  signature, so every caller takes a `model` argument (no patching of LiteLLM in agent tests). Sets the
  no-network env (REQ-005) before importing LiteLLM.
- **MCP client** (`mcp_client.py`): `McpTools` opens one stdio session to `python -m agent_lab.mcp_server` (venv
  Python, folder settings passed as env), exposes `specs()` (OpenAI tool format), `call(name, args)` and
  `close()`; it is a context manager so the child process always ends.
- **Tool bridge** (`tools_schema.py`): converts MCP `Tool(name, description, inputSchema)` to
  `{"type": "function", "function": {...}}`; `check_args(schema, args) -> list[str]` checks required keys,
  unknown keys and JSON types (small, local; no extra package).
- **MCP server**: FastMCP tools return plain values; bad input raises `ToolError` with a helpful message, which
  FastMCP turns into an error result (`isError: true`). Folder paths come from settings via env set by the client.
- **Agents**: `run(question, *, model, tools, trace=None, max_steps=6) -> RunResult(text, steps, stopped_by)`.
  A step is one model call. The graph agent gets `ChatLiteLLM` in production and `FakeChatModel` in tests, uses
  `recursion_limit = 2 * max_steps`, and turns `GraphRecursionError` into the shared `LIMIT_MESSAGE`.
  Lesson 05 and `McpTools` read resources only when `resources/list` offers them.
- **Trace**: `Trace(path).write(kind, **fields)`; `t` from `time.monotonic()` relative to run start.
- **Viewer**: static HTML + inline JS; reads the file with `FileReader`; no fetch, no CDN.

## Data
No database. Files only: settings TOML, notes (`sandbox/notes/*.md`), docs corpus (`docs_corpus/*.md`), traces
(`runs/*.jsonl`), the model server pid and log (`.agent-lab/`).

Concurrency: two chats at once are allowed. Each has its own MCP child and trace file; llama-server queues
requests; notes are last-write-wins (a learning sandbox, no locking).

## Hosting and network
This PC only. `llama-server` binds `127.0.0.1:8090` (harness reserves 8080, 8081, 8083, 8084). MCP uses stdio
(no port). No outbound network at run time: LiteLLM's remote cost map is switched off (REQ-005; it has no telemetry
switch on 1.106.6, D-013 notes), FastMCP's banner and its pypi.org update check are off (`show_banner=False`,
`FASTMCP_CHECK_FOR_UPDATES=off`; found at AL-F-005), and a socket guard enforces this in tests. One GPU model at a time; `agent-lab model stop` when idle.

## Risks
- Small model picks wrong tools or arguments: argument checks + error feedback + step limit (REQ-030).
- `response_format` json_schema works on this llama-server build (MEASURED 2026-10-30, Qwen3-1.7B: 2 of 2 valid
  with it, 2 of 2 invalid without it; lesson 03 live 3 of 3). Lesson 03 still validates and retries once.
- LiteLLM passing `tools` unchanged to the openai-compatible endpoint is UNVERIFIED: live smoke test REQ-051.
- Supply chain: LiteLLM had malicious PyPI releases in 2026 (UNVERIFIED versions 1.82.7/1.82.8): exact pin +
  hashes, reviewed before install, logged in DEPENDENCIES.md.
