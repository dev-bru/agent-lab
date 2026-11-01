# Agent Lab: product spec

Status: draft for the SPEC GATE (2026-10-29). Sources: `plan/01-brainstorm.md` (human answers),
`plan/02-research.md`, `plan/03-architecture.md`.

## Vision
A small, local codebase that teaches how an AI agent works by letting the learner read and run each part:
model API calls, tool calling, structured output, the agent loop and MCP. Everything runs on this PC. Then the same
agent is rebuilt with LangGraph, so the learner sees exactly what a framework does for them.

## User
One learner (the human) on this Windows 10 PC (4 cores, 4 GB GPU), reading the code and running it from a terminal.
Knows Python. New to agent internals.

## Success
1. Each lesson 01-06 runs alone with one command and prints a clear result in under 30 s on this PC (model warm).
2. The finished app answers a question that needs two tools in a row, and its trace replays in the viewer.
3. The hand-written agent and the LangGraph agent give the same tool sequence for the same scripted (fake) model.
4. `uv run pytest` passes with no model server running (fake model only).
5. Every source file has plain-English comments (eli5 level, ASD-STE100 style).

## Journeys
- **Learn one idea.** `uv run agent-lab model start` -> `uv run python lessons/02_tool_call.py` -> read the
  printed steps -> read the commented source -> open the matching flow in `plan/03-architecture.html`.
- **Use the agent.** `uv run agent-lab chat` -> ask questions -> each answer prints a trace path -> open
  `viewer.html` and load the trace to replay model calls, tool calls, errors and timings.
- **Compare builds.** `uv run agent-lab chat --engine graph` vs `--engine hand` on the same question; compare traces.
- **Test without a GPU.** `uv run pytest` uses a scripted fake model (`--fake` runs any lesson or the chat the
  same way); `uv run pytest -m live -n 0` runs the opt-in smoke
  tests against the running `llama-server`.

## Scope
**Must**
- Lessons `01_model_call`, `02_tool_call`, `03_structured_output`, `04_agent_loop`, `05_mcp_client`,
  `06_langgraph_agent`, each runnable alone.
- FastMCP server with four tool groups: math and units; notes in a sandbox folder; date and time; local docs search.
- Hand-written agent loop on LiteLLM with argument checks, error feedback and a step limit.
- The same agent in LangGraph (ChatLiteLLM + our own small MCP adapter, D-012).
- CLI chat app with both engines; `--fake` mode for every lesson and the chat.
- No outbound network: LiteLLM remote lookups off, enforced by a test socket guard (REQ-005).
- Run trace files (JSON lines) and a single-file HTML trace viewer.
- pytest suite with a scripted fake model; opt-in live smoke tests.
- Plain-English comments everywhere; the interactive diagrams (`plan/03-architecture.html`) linked from the README.
- `agent-lab model start|stop|status`: starts and stops `llama-server` with the pinned model. Paths come from
  `agent-lab.toml` (no hard-coded user paths).

**Should**
- MCP resource `docs://{name}` and one MCP prompt (REQ-025).

**Won't (v1)** (ASSUMPTION, the human picked none; confirm at the gate)
- Cloud models or API keys. Internet tools. A web chat UI. A vector database or long-term memory.

## Cost and constraints
INR 0 per month: no accounts, no API keys, no cloud. Runs on this PC only (4 cores, 4 GB GPU, Windows 10).

## UI / UX notes
- Terminal output is short and labelled: `you>`, `agent>`, `[tool: name]`, `[step 2/6]`.
- Errors say what to do: "Model server not running on 127.0.0.1:8090. Start it: `uv run agent-lab model start`."
- The trace viewer is one HTML file with no network access: open it, pick a trace file, step through events.
  Works in dark and light mode.
