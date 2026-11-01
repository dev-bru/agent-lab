# Phase 2: MCP tool server (F-005..F-008, F-018)

Status: planned (2026-10-29). One feature at a time through /delegate; spec per feature from
the harness template; evaluator review; `verify_feature.py` sets status.

## Features (in order)
1. F-005 math, units, date and time tools
2. F-006 sandboxed notes tools
3. F-007 docs search, resource, prompt
4. F-008 MCP protocol test + lesson 05
5. F-018 docs resource + explain_tool prompt (Should; skip if time is short)

## Done when
`uv run python lessons/05_mcp_client.py` lists 9 tools over stdio; no model needed.
Full `uv run pytest` green after every feature.

## Notes
- F-005..F-007 touch one file (`mcp_server.py`): run them one at a time, never as parallel writers.
