# Phase 1: Foundation (F-001..F-004)

Status: planned (2026-10-29). One feature at a time through /delegate; spec per feature from
the harness template; evaluator review; `verify_feature.py` sets status.

## Features (in order)
1. F-001 project setup, settings, DEPENDENCIES.md
2. F-002 model server control
3. F-003 model client + fake model
4. F-004 lesson 01

## Done when
`uv run agent-lab model start` then `uv run python lessons/01_model_call.py` answers a question; `uv run pytest` green.
Full `uv run pytest` green after every feature.

## Notes
- Install the pinned packages only after the human approves the dependency list (harness rule 8).
