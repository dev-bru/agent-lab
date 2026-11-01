# Agent Lab: decisions

Each entry: what, who decided, why. "Human" = answered in the intake interview (2026-10-29).
ASSUMPTION entries are Claude's defaults; the human confirms or changes them at the SPEC GATE.

## D-001 Agent built twice: by hand on LiteLLM, then in LangGraph (human, brainstorm round 1)
The by-hand loop shows every moving part; the LangGraph version shows what an industry framework replaces.
Both use LiteLLM underneath (LangGraph through `ChatLiteLLM`), so the comparison isolates the framework.

## D-002 Model: Qwen3 1.7B on llama.cpp `llama-server` (human, round 1; runtime changed after a check)
The idea named Ollama. Ollama is not installed; the llama.cpp CUDA build in a local folder is, and it returned
OpenAI-style tool calls in 1.26 s (MEASURED). The human agreed to use it. Port 8090.

## D-003 Tools through an own FastMCP server, stdio transport (human, round 1)
Tool groups: math and units, sandbox notes, date and time, local docs search. Stdio needs no port.

## D-004 Interface: CLI chat + per-run trace + HTML trace viewer (human, round 1)

## D-005 Layout: numbered lessons 01-06 plus one app (human, round 2)

## D-006 Tests: scripted fake model; opt-in live smoke tests (human, round 2)

## D-007 Python 3.12 via uv; exact pins with hashes (harness default + research)
LiteLLM had compromised PyPI releases in 2026 (UNVERIFIED detail), so every version is pinned and reviewed.

## D-008 Settings file instead of hard-coded paths (Claude, harness portability rule)
The llama-server and model paths differ per machine; `agent-lab.toml` + env overrides keep code portable.

## D-009 Own small argument checker, no jsonschema dependency (Claude, ponytail rule)
Tool schemas here are flat (numbers and strings). Checking required keys, unknown keys and basic types is a few
lines. Add `jsonschema` only if a tool needs nested schemas.

## D-010 Spec audit 1 fixes (Claude, 2026-10-29)
Fake model ships in `src/` (lessons use `--fake`); one canonical two-tool task; a step is one model call and
both agents share one limit message; LiteLLM's remote cost map and telemetry off, socket guard in tests;
`tzdata` added; docs resource and prompt split into REQ-025 (Should, F-018); the cloud-model example dropped
(it conflicted with the local-only rule).

## D-011 SPEC GATE approved (human, 2026-10-29, dashboard Plan view)
The human approved the plan and confirmed assumptions A-1..A-6 (feedback.jsonl, ts 1793295961).

## D-012 Install approved; own MCP-to-LangChain adapter (human, 2026-10-31)
The human approved installing the pinned packages (exact versions, hashes in `uv.lock`). Locking showed that
FastMCP 4.1.4 needs `mcp>=2.3` while langchain-mcp-adapters 0.3.2 (newest) needs `mcp<2`: they cannot coexist
(MEASURED with `uv lock`). The human chose to drop langchain-mcp-adapters: the LangGraph agent wraps our own
`McpTools` as LangChain tools in a few lines, so lesson 06 shows what an adapter does. Every other approved version
is unchanged (129 packages resolve, mcp 2.3.0). DOCUMENTED (langchain-litellm requires_dist, PyPI 2026-10-31):
litellm 1.82.7 and 1.82.8 are excluded upstream, which confirms the 2026 incident; our pin 1.106.6 is unaffected.

## ASSUMPTIONS (confirmed at the SPEC GATE, D-011)
- A-1 Won't in v1: cloud models or API keys, internet tools, a web chat UI, a vector DB or long-term memory.
- A-2 Trace viewer test uses Python Playwright with the installed Chrome (no browser download).
- A-3 The model file stays in a shared models folder (shared with the harness benchmark); the settings file points
  to it. No copy into the project.
- A-4 Max 6 model calls per question by default.
- A-5 Live tests: a test passes if 1 of up to 3 attempts passes (small models are not deterministic).
- A-6 Two chats at once are allowed; notes are last-write-wins.

## D-013 Thinking off through the template flag, not `/no_think` (human, 2026-10-30)
MEASURED 2026-10-30 on Qwen3-1.7B-Q8_0 with llama-server build 11408 (`--jinja`): with `/no_think` in the messages,
the model's tool call is returned inside `reasoning_content` as raw `<tool_call>` text and `tool_calls` is empty
(4 of 4 tries). With `chat_template_kwargs: {"enable_thinking": false}` the tool call is parsed (1.0 s direct,
3.3 s through LiteLLM `extra_body`, cold) and plain text answers in 0.1 s; thinking on also parses tools but takes
about 4 s. Decision: `chat()` keeps `thinking=False` as the default and sends the template flag; REQ-004 AC2 updated.
The human confirmed thinking stays off.

## D-014 Parallel offline tests with pytest-xdist (human, 2026-10-31)
MEASURED 2026-10-31: the offline suite took 243 s after AL-T-004; about 40 tests each start a new Python process
and an MCP server. A first `-n auto` run (4 workers) took 135 s. Options: pytest-xdist (new dev package), or move
the CLI and lesson tests in-process (no package, about 140 s estimated, bigger rewrite), or relax REQ-050. The human
chose pytest-xdist 3.8.0 (with execnet 2.1.2) and installed it. Live tests stay serial (`-n 0`): they share one
model server.

## D-015 No test-speed goal; prepare a public release (human, 2026-11-01)
The human: test speed does not matter for a learning project. REQ-050 keeps "offline, no model, no network" and
drops the 60 s target (MEASURED: about 130 s with 4 workers). The repo is cleaned for a public release: MIT
licence, a full README for learners, no machine-specific paths, and the build files (plan, specs, decisions) kept
and explained in the README. The public repo starts from one fresh commit, so the local history and its author
emails stay private.
