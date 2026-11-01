# Agent Lab: requirements

Status: draft for the SPEC GATE (2026-10-29), revised after spec audit 1. Priority: M = must, S = should.
Source: B1/B2 = brainstorm round 1/2 answer, R = research, A = assumption (confirm at gate), H = harness rule,
AU = spec audit.

## Shared definitions
- **Fake model**: `agent_lab.fakes.FakeModel(script)`, shipped in `src/` because lessons and the CLI use it with
  `--fake`. It has the same `chat()` signature as the real model (REQ-004), returns scripted replies in order and
  records every request. `agent_lab.fakes.FakeChatModel(script)` wraps the same script as a LangChain chat model
  (supports `bind_tools`) for the graph agent.
- **Fake script format**: a JSON file holding a list of replies. Each reply is `{"text": str}` or
  `{"tool_calls": [{"name": str, "arguments": str}]}` (`arguments` is a JSON string, as from a real model). Call
  ids are generated `call_1`, `call_2`, ... A finished script raises `ScriptExhausted`.
- **`--fake [SCRIPT]`**: every lesson and `agent-lab chat` accept it. No path = the built-in script for that
  lesson in `src/agent_lab/fake_scripts/`.
- **Canonical two-tool task** (used by REQ-013, 030, 031, 040, 051): question
  `What is 17 times 23? Save the answer as a note called result.` Expected tool sequence:
  `multiply {"a": 17, "b": 23}` -> `write_note {"name": "result", "text": <contains "391">}` -> final text containing
  `391`. Fake script: `fake_scripts/two_tool.json`.
- **Step**: one model call. `max_steps` (default 6) caps model calls per question in both agents.
- **Limit message**: the constant `agent_lab.agent.LIMIT_MESSAGE` = `Stopped: reached the step limit (N model
  calls).` Both agents return it with `stopped_by="limit"`.
- **Error result**: an MCP tool result with `isError: true` and a message that says what was wrong and what is
  valid. No exception leaves the MCP server.

## Foundation
**REQ-001 (M, B1/R) Project setup.** Python 3.12, uv, package `agent_lab` under `src/`, console script
`agent-lab`. Runtime dependencies are exact pins (`==`); `uv.lock` holds hashes. `tzdata` is a dependency
(Windows has no system time-zone database).
- AC1: `uv sync --locked` succeeds on a fresh clone.
- AC2: a test parses `pyproject.toml`: every runtime dependency uses `==`; `tzdata` is present.
- AC3: `uv run agent-lab --help` lists the commands `chat` and `model`.

**REQ-002 (M, H) Settings, no hard-coded user paths.** `agent-lab.toml` (example committed as
`agent-lab.example.toml`) holds: `llama_server` path, `model` path, `host` (default `127.0.0.1`), `port` (8090),
`model_name` (`qwen3-1.7b`), `max_steps` (6), `timeout_s` (120), `notes_dir` (`sandbox/notes`), `docs_dir`
(`docs_corpus`), `runs_dir` (`runs`). Env vars `AGENT_LAB_<KEY>` (upper case) override the file.
- AC1: a test loads the example file and gets the defaults above.
- AC2: `AGENT_LAB_PORT=9999` gives port 9999; a non-integer port gives an error naming the key.
- AC3: a test scans `src`, `lessons`, `tests` for `C:\Users` and drive-letter paths and finds none.

**REQ-003 (M, B1/AU) Model server control.** `agent-lab model start|stop|status`.
- `start` runs `<llama_server> -m <model> --jinja -ngl 99 -c 8192 --host <host> --port <port>` as a detached
  process (Windows `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`), output to `.agent-lab/model.log`, writes the pid
  to `.agent-lab/model.pid`, then polls `GET /health` until OK (max 120 s).
- `status` prints `running` only if the pid is alive AND `/health` is OK; otherwise `stopped`. A pid file whose
  process is gone is deleted.
- `stop` runs `taskkill /PID <pid> /T /F` and deletes the pid file.
- AC1 (unit, no process): the built command line equals the list above for the example settings.
- AC2: a host other than `127.0.0.1`/`localhost` is refused, exit 1.
- AC3: missing `llama_server` or `model` file: exit 1, message names the setting and the path.
- AC4: `start` when already running prints `already running`, exit 0. Port used by another process: exit 1 with
  the port in the message (unit test with a socket bound on a free port).
- AC5: stale pid file -> `status` prints `stopped` and the file is gone. `stop` when stopped prints
  `already stopped`, exit 0.
- AC6 (live): start -> status `running` -> stop -> status `stopped`.

**REQ-004 (M, B1/AU) Model client.** `agent_lab.model.chat(messages, tools=None, response_format=None,
thinking=False) -> Reply` calls `litellm.completion(model="openai/<model_name>", api_base="http://<host>:<port>/v1",
api_key="local", timeout=<timeout_s>, ...)`. `Reply` = `text`, `tool_calls: list[ToolCall(id, name, arguments)]`,
`usage`. Thinking stays off by default: when `thinking` is false (the default), the call adds
`extra_body={"chat_template_kwargs": {"enable_thinking": False}}`; messages are sent unchanged (D-013).
- AC1: with `litellm.completion` patched, the recorded kwargs match the settings, including `timeout`.
- AC2: `thinking=False` -> `extra_body` carries `enable_thinking: False` and the messages are unchanged;
  `thinking=True` -> no `extra_body`.
- AC3: connection refused -> `ModelServerDown`; message names host, port and `agent-lab model start`.
- AC4: timeout -> `ModelTimeout` naming `timeout_s`; HTTP 400 (for example context too long) -> `ModelError`
  carrying the server's message.

**REQ-005 (M, H/AU) No outbound network.** Before importing LiteLLM, `agent_lab.model` sets
`LITELLM_LOCAL_MODEL_COST_MAP=True` and adds `127.0.0.1,localhost` to `NO_PROXY`. (`litellm.telemetry` does not exist on 1.106.6: MEASURED 2026-10-30 at F-003.)
- AC1: the default test suite runs with an autouse socket guard (`tests/conftest.py`) that fails any connect to a
  non-loopback address; the suite passes.
- AC2: a test imports `agent_lab.model` under the guard without error, then asserts
  `LITELLM_LOCAL_MODEL_COST_MAP == "True"` and `NO_PROXY` contains `127.0.0.1`.

## Lessons
Each lesson is `lessons/NN_name.py`, runs alone (`uv run python lessons/NN_name.py`), prints labelled steps
(`you>`, `agent>`, `[tool: name]`, `[step n/max]`), and accepts `--fake [SCRIPT]`.

**REQ-010 (M, B1) Lesson 01: model call.** One system + user message; prints the request, reply text, token counts.
- AC1: `--fake` exits 0 and prints `agent>` followed by the fake reply.

**REQ-011 (M, B1) Lesson 02: tool call.** Local `multiply` with an OpenAI-format schema; shows the `tool_calls`
reply, runs the tool, sends a `role: tool` message with the same id, prints the final answer.
- AC1: `--fake` prints `[tool: multiply]` and `391`.
- AC2: the second recorded request contains a `tool` message whose `tool_call_id` equals the first call's id.

**REQ-012 (M, B1) Lesson 03: structured output.** Pydantic `StudyCard(term: str, meaning: str <= 200 chars,
example: str)`; schema sent as `response_format`; validate; on failure retry once with the validation error
text; second failure prints the error, exit 1.
- AC1: fake `[bad, good]` -> exit 0, card printed, exactly 2 model calls.
- AC2: fake `[bad, bad]` -> exit 1, error printed, exactly 2 model calls.

**REQ-013 (M, B1) Lesson 04: agent loop.** Runs the hand agent (REQ-030) on the canonical task and prints each step.
- AC1: `--fake` prints `[tool: multiply]`, `[tool: write_note]` and a final answer containing `391`.

**REQ-014 (M, B1) Lesson 05: MCP client.** Starts the MCP server over stdio; prints server info, the tool list
(name + one line), calls `multiply`, then reads `docs://mcp-basics` only if `resources/list` offers it, else prints
`no resources offered`.
- AC1: exits 0 (no model needed), lists all 9 tools and prints `391`.
- AC2: prints the resource text when the server offers it, or `no resources offered` when it does not (both
  tested with a server built with and without REQ-025).

**REQ-015 (M, B1) Lesson 06: LangGraph agent.** Runs the graph agent (REQ-031) on the canonical task and prints
each node update.
- AC1: `--fake` prints node updates `model, tools, model, tools, model` in that order and the final answer.

## MCP tool server
`agent_lab.mcp_server` is a FastMCP server (`python -m agent_lab.mcp_server`, stdio). Every tool has type hints
and a one-line docstring. Exactly 9 tools: `add`, `multiply`, `convert_units`, `write_note`, `read_note`,
`list_notes`, `now`, `days_between`, `search_docs`.

**REQ-020 (M, B1) Math and units.** `add(a, b)`, `multiply(a, b)`, `convert_units(value, from_unit, to_unit)` for
length (mm, cm, m, km, in, ft, mi), mass (g, kg, lb), temperature (C, F, K).
- AC1: `multiply(17, 23) == 391`; `convert_units(1, "mi", "km") == 1.609344` (6 places); `0 C -> 32 F`.
- AC2: unknown unit, or units of different kinds (km -> kg), give an error result listing the valid units.

**REQ-021 (M, B1/AU) Notes in a sandbox.** `write_note(name, text)`, `read_note(name)`, `list_notes()` work only in
`notes_dir`. Names match `^[A-Za-z0-9_-]{1,64}$` and are not Windows device names (CON, PRN, AUX, NUL, COM1-9,
LPT1-9, any case). Files are `<name>.md`, UTF-8. Max 10,000 characters. Writing an existing name replaces it and
says `updated`. The folder is created on first write. Before any file access, the resolved real path must be
inside the resolved `notes_dir` (blocks junction and symlink escapes).
- AC1: write -> read returns the same text (including non-ASCII); list includes the name; second write says `updated`.
- AC2: names `../x`, `a/b`, `C:x`, `con`, `Com1`, empty, 65 characters -> error result; the parent folder is
  unchanged.
- AC3: 10,000 characters accepted; 10,001 -> error result.
- AC4: a junction inside `notes_dir` pointing outside (created by the test with `cmd /c mklink /J`, no admin
  needed) -> error result, no file written outside. The test never skips.
- AC5: missing note -> error result; `list_notes()` on a missing folder -> empty list.

**REQ-022 (M, B1/AU) Date and time.** `now(timezone="UTC")` returns ISO 8601 with offset (IANA names via
`zoneinfo` + `tzdata`). `days_between(start, end)` takes `YYYY-MM-DD`, returns whole days `end - start`
(negative when end is before start).
- AC1: `days_between("2026-10-29", "2026-12-31") == 63`; reversed gives `-63`.
- AC2: `now("Asia/Kolkata")` ends with `+05:30`.
- AC3: bad date or unknown zone -> error result naming the expected format.

**REQ-023 (M, B1/AU) Docs search.** `search_docs(query, limit=3)` searches `*.md` in `docs_dir`: case-insensitive
whole-word match of the query's words, ranked by hit count, ties by file name. Returns up to `limit` items
`{file, line, text}` (best line per file).
- AC1: a word present in one fixture doc returns that file first; an absent word returns `[]`.
- AC2: empty or whitespace query, or `limit` outside 1..10 -> error result.

**REQ-024 (M, R) MCP protocol test.** An in-memory FastMCP client lists tools and calls each tool once.
- AC1: the tool names equal the 9 above.

**REQ-025 (S, B1/AU) Docs resource and prompt.** Resource `docs://{name}` returns the text of `<name>.md` in
`docs_dir` (name rule as REQ-021); prompt `explain_tool(tool_name)`.
- AC1: `docs://mcp-basics` returns the fixture text; `docs://missing` and `docs://..%2Fx` give errors.
- AC2: `explain_tool("multiply")` returns a prompt that contains the tool's description.

## Agents
Both agents: `run(question, *, model, tools, trace=None, max_steps=6) -> RunResult(text, steps,
stopped_by: "answer" | "limit")`. `tools` is an `agent_lab.mcp_client.McpTools` (open MCP session: `specs()` in
OpenAI format, `call(name, args) -> (text, is_error)`). `trace` is an `agent_lab.trace.Trace` or None.

**REQ-030 (M, B1/AU) Hand-written agent (`agent_lab.agent.hand`).** Loop at most `max_steps` model calls: send the
history and all tool specs; no tool calls -> return the text. For each tool call: parse `arguments` (bad JSON is
an error), check them against the schema (required keys, unknown keys, JSON types), call valid ones through
`tools`, and add a `tool` message with the result or the error text. Unknown tool -> error listing valid names.
- AC1 (fake): canonical task -> tool sequence as defined, final text contains `391`, 3 model calls.
- AC2 (fake): wrong argument name -> error `tool` message; next call succeeds; no exception.
- AC3 (fake): arguments that are not valid JSON -> error `tool` message; no exception.
- AC4 (fake): unknown tool -> error `tool` message listing the 9 names.
- AC5 (fake): always-tool model -> `stopped_by="limit"`, text = `LIMIT_MESSAGE`, exactly `max_steps` model calls.

**REQ-031 (M, B1/AU) LangGraph agent (`agent_lab.agent.graph`).** `build(chat_model, tools) -> graph`: `START ->
model -> tools_condition -> (tools | END)`, `tools -> model`. Production passes `ChatLiteLLM` (same settings as
REQ-004) and LangChain tools built by `agent_lab.agent.graph.as_langchain_tools(mcp_tools)` (our own adapter, D-012:
one `StructuredTool` per MCP tool, args schema from the MCP input schema, calling `McpTools.call`); tests pass `FakeChatModel`. `run()` invokes with
`recursion_limit = 2 * max_steps` (one model plus one tools superstep per step; the next model call would
exceed it) and catches `GraphRecursionError` -> `stopped_by="limit"`, `LIMIT_MESSAGE`.
Tool errors become `ToolMessage`s with the same text as REQ-030.
- AC1 (fake): canonical task -> same tool name + argument sequence and final text as REQ-030 AC1.
- AC2 (fake): always-tool model -> same result as REQ-030 AC5 (`max_steps` model calls).

## App, trace, viewer
**REQ-040 (M, B1/AU) CLI chat.** `agent-lab chat [--engine hand|graph] [--fake [SCRIPT]]`: reads lines, answers,
prints `[tool: name]` lines and the trace path. `exit`, end of input or Ctrl+C quit with exit 0 and close the MCP
child process.
- AC1: piping two questions + `exit` with `--fake` gives two answers, exit 0.
- AC2: no model server -> the REQ-004 AC3 message, exit 2, no traceback.
- AC3: after exit (and after a simulated `KeyboardInterrupt`), the MCP child process is no longer running.

**REQ-041 (M, B1/AU) Run trace.** Each run writes `<runs_dir>/<UTC YYYYMMDDTHHMMSS_mmm>-<engine>.jsonl` (if the
name exists, add `-2`, `-3`, ...). One JSON object per line: `t` (seconds since start, from `time.monotonic()`),
`kind` (`user | model_request | model_reply | tool_call | tool_result | error | final | limit`) plus kind fields.
The graph agent writes the same kinds from `graph.stream(stream_mode="updates")`.
- AC1: every line of a fake run parses, has `t` and `kind`; `t` never decreases.
- AC2: hand and graph fake runs of the canonical task give the same `kind` sequence.
- AC3: two runs started in the same millisecond get different files.

**REQ-042 (M, B1/AU) Trace viewer.** `viewer/viewer.html`: one file, no network requests. File picker loads a
trace; event list; step forward and back; selected event's JSON; theme toggle (dark/light). Keyboard usable
(arrow keys step, visible focus).
- AC1: a Playwright test (Python, installed Chrome channel) loads a fixture trace and sees the right event count
  and the `final` text.
- AC2: zero network requests besides the page (request log).
- AC3: the theme toggle changes `data-theme` on `<html>` and the background colour.
- AC4: without Chrome the tests fail (not skip) with `Chrome not found: install Chrome or set the channel`.
  F-001 records the Chrome check in DEPENDENCIES.md.

## Non-functional
**REQ-050 (M, NFR, B2/AU) Offline tests.** `uv run pytest` needs no model server, GPU or network, including the
stdio and browser tests. Run time is not a goal (D-015: a learning project). Feature gates require 0 skipped tests
(`pytest -rs`). Live tests carry `@pytest.mark.live` and are
deselected by default (`addopts = -m "not live"`).
- AC1: the default run reports 0 live tests executed.

**REQ-051 (M, NFR, B2/AU) Live smoke tests.** `uv run pytest -m live -n 0` with the model server running. Covers:
lessons 01-06 (exit 0), the hand and graph agents on the canonical task (tool sequence as defined), REQ-003 AC6.
Each test must finish in 30 s (warm model). A small model is not deterministic: a test passes if 1 of up to 3
attempts passes; the report shows the attempt count. On failure the test prints the last model reply and the
trace path.
- AC1: all live tests pass on this PC.

**REQ-052 (M, NFR, B1/AU) Plain-English comments.** Every module, public class and public function under `src/`
and `lessons/` has a docstring. Docstring sentences have at most 20 words. Lessons explain each step in a comment
before its code. Tone (eli5, ASD-STE100) is checked in review.
- AC1: an AST test finds no missing docstrings and no docstring sentence over 20 words.

**REQ-053 (M, NFR, H/A) Local only.** No code calls a host other than `127.0.0.1`/`localhost`; no API keys are
read. (A) No internet tools, web chat UI or vector DB.
- AC1: a test scans `src` and `lessons` for `http://`/`https://` and allows only `127.0.0.1`/`localhost` URLs
  and URLs inside comments.
- AC2: REQ-005 AC1.

**REQ-054 (M, NFR, H/AU) Dependency record.** `docs/DEPENDENCIES.md` lists every dependency: Python packages,
the llama.cpp build (number + commit), the model file (source, commit, licence, size, SHA-256).
- AC1: every package in `pyproject.toml` appears in DEPENDENCIES.md; a llama.cpp row and a model row exist.
- AC2 (live): the SHA-256 of the configured model file equals the one in DEPENDENCIES.md.

**REQ-055 (M, NFR, B1/AU) README.** A numbered Setup list of at most 10 items; a lessons table naming every lesson
file with its diagram tab (`plan/03-architecture.html`, tab N); the command list.
- AC1: a test counts at most 10 Setup items and finds every lesson file name with a `tab` reference.
