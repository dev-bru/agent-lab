# Agent Lab: SPEC GATE summary

Status: waiting for your approval (2026-10-29). Nothing is built or installed yet.

## What you approve
A local learning project: one small model on this PC (Qwen3 1.7B on llama-server, port 8090), your own FastMCP
tool server (9 tools: math and units, sandbox notes, date and time, docs search), and one agent written twice:
by hand on LiteLLM, then with LangGraph. Six numbered lessons, a terminal chat, run traces and an HTML trace
viewer. Tests use a scripted fake model, so they need no GPU; live tests are opt-in.

## Documents
- `docs/PRODUCT_SPEC.md`: vision, journeys, scope (Must / Should / Won't), cost INR 0.
- `docs/REQUIREMENTS.md`: REQ-001..055, each with testable acceptance criteria.
- `docs/ARCHITECTURE.md`: stack (and what was rejected), layout, contracts, risks.
- `docs/DECISIONS.md`: D-001..D-010 and assumptions A-1..A-6.
- `feature_list.json`: F-001..F-019, all failing, in 4 phases (`docs/exec-plans/phase-1..4.md`).
- `plan/03-architecture.html`: interactive diagram of the six flows.

## Assumptions to confirm
- A-1 Won't in v1: cloud models or API keys, internet tools, a web chat UI, a vector DB or long-term memory.
- A-2 Viewer tests use Python Playwright with the installed Chrome (no browser download).
- A-3 The model file stays in the shared benchmark models folder; the settings file points to it.
- A-4 Max 6 model calls per question.
- A-5 Live tests pass if 1 of up to 3 attempts passes.
- A-6 Two chats at once are allowed; notes are last-write-wins.

## Reviews
Spec auditor: 2 rounds. Round 1 found 17 items, round 2 found 6. All are fixed. Examples: LiteLLM's hidden
download of a price list from GitHub is now switched off and blocked by a test; the step limit is the same in
both agents; the notes sandbox also blocks junction escapes.

## After approval
1. Record the approval in DECISIONS.md and commit the plan in the agent-lab repo.
2. Ask you to approve the dependency install (exact versions with hashes): fastmcp 4.1.4, litellm 1.106.6,
   langgraph 1.2.18, langchain-mcp-adapters 0.3.2, langchain-litellm 0.11.2, plus pydantic, tzdata, pytest,
   playwright (versions picked at setup).
3. Phase 1, F-001 first, through Codex with evaluator review.
