# Agent Lab: brainstorm

Status: draft (2026-10-29). Rounds: 2 of 3. Every answer below is the human's unless marked ASSUMPTION.

## Why this project
A learning project for agentic AI fundamentals that runs fully on this PC. The human wants to understand, by
reading and running code, how an agent works: model APIs, tool calling, structured outputs, agent loops and MCP.
It is also a real end-to-end test of the harness and dashboard v3 (screenshots of every page while it is built).

## Goals
1. Learn each fundamental in a small, runnable step, then see them combined in one working agent.
2. Build an own MCP server (FastMCP) with a catalog of simple tools, and connect the agent to it.
3. See the same agent written by hand and with an industry framework, to understand what the framework does.
4. Read plain-English comments everywhere (eli5 level, ASD-STE100 style) and interactive diagrams of each flow.

## Users
One learner (the human), on this Windows PC, reading the code and running it from the terminal.

## Decisions from the interview
| Topic | Answer (round) |
|---|---|
| Agent build | By hand first (plain Python loop on LiteLLM), then the same agent in LangGraph (1) |
| Model | Qwen3 1.7B (1). Runtime changed after a check: no Ollama on this PC; llama.cpp `llama-server` from a local folder (build 11408) serves an OpenAI-compatible API; the human agreed |
| MCP tool catalog (FastMCP) | Math and units; notes in a sandbox folder; date and time; local docs search (1) |
| Interface | CLI chat + a per-run trace file replayed by an HTML trace viewer (1) |
| Layout | Numbered lessons (01 model call ... 06 LangGraph agent), each runs alone, plus one finished agent app (2) |
| Tests | pytest with a scripted fake model for exact, fast tests; opt-in live smoke tests against llama-server (2) |

## MEASURED on this PC (2026-10-29)
- Model file `Qwen3-1.7B-Q8_0.gguf` (Qwen/Qwen3-1.7B-GGUF, commit 90862c4b, Apache-2.0), 1,834,426,016 bytes,
  SHA-256 061b54da...6590cb1a matches the published value. Stored in a shared models folder.
- `llama-server --jinja -ngl 99 -c 8192 --port 8090` on the 4 GB GPU: one `/v1/chat/completions` request with a
  `multiply` tool returned `tool_calls: multiply {"a": 17, "b": 23}`, finish reason `tool_calls`, in 1.26 s.

## Scope
- Must: lessons 01-06, MCP server with the four tool groups, the hand-written agent, the LangGraph agent, CLI,
  trace files and the trace viewer, fake-model tests, comments, diagrams.
- Should: MCP resources (docs) and one MCP prompt; a LiteLLM config that shows where a cloud model would plug in.
- Won't (ASSUMPTION, the human picked none; confirm at the SPEC GATE): cloud models or API keys (also a harness
  rule); internet tools; a web chat UI; a vector database or long-term memory.

## Options considered
- Agent framework: LangGraph (chosen, step 2), OpenAI Agents SDK, by-hand only. LangGraph won as the common
  industry choice for graph-shaped agents; the by-hand step keeps every moving part visible.
- Runtime: Ollama (not installed) vs llama.cpp server (already on the PC, GPU build, verified). llama.cpp chosen.
- Layout: lessons + app (chosen), one app only, notebooks (adds Jupyter).

## Open questions (for research)
- Exact pinned versions of FastMCP, LiteLLM, LangGraph (and langchain-core), MCP Python SDK; their licences.
- LiteLLM's provider string for an OpenAI-compatible local server; does it pass `tools` unchanged?
- How LangGraph's tool node talks to an MCP server (langchain-mcp-adapters or by hand).
- Qwen3 thinking mode: how to turn it off per request on llama-server (`/no_think`, `chat_template_kwargs`).
- Python version (harness default: 3.12 via uv).
