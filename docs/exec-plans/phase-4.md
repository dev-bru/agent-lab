# Phase 4: Framework and app (F-013..F-017, F-019)

Status: planned (2026-10-29). One feature at a time through /delegate; spec per feature from
the harness template; evaluator review; `verify_feature.py` sets status.

## Features (in order)
1. F-013 LangGraph agent
2. F-014 lesson 06
3. F-015 CLI chat
4. F-016 HTML trace viewer
5. F-017 local-only check, README
6. F-019 live smoke tests (Claude runs them with the model server up, then stops it)

## Done when
`uv run agent-lab chat --engine graph` answers a two-tool question; the viewer replays its trace; `pytest -m live` passes.
Full `uv run pytest` green after every feature.

## Notes
- F-016 is front-end: screenshot dark and light at 1440 and 360 px. `pytest -m live` is run by Claude with the model server up, then the server is stopped.
