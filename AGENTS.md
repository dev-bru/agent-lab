# AGENTS.md: map of agent-lab

Learning project: a local AI agent (Qwen3 1.7B on llama-server) built by hand on LiteLLM, then with LangGraph,
using its own FastMCP tool server. Built through the crosscheck harness (Claude orchestrates, Codex implements).

## Rules
1. Local only: no cloud models, API keys, internet tools or hosts other than 127.0.0.1/localhost.
2. Only touch files listed in the task spec. Never weaken tests. Status in feature_list.json changes only via the
   harness `verify_feature.py`.
3. Exact dependency pins; log every dependency in docs/DEPENDENCIES.md. No installs without human approval.
4. Plain-English comments (eli5 level, ASD-STE100 style) on every module and public function.
5. Tests never need the model server; live tests are marked `@pytest.mark.live`.
6. One GPU model at a time; stop llama-server when idle. Port 8090.
7. Native Windows; pathlib; UTF-8, LF.

## Map
| Path | What |
|---|---|
| progress.md | Current state, next step |
| docs/PRODUCT_SPEC.md | Vision, scope, journeys |
| docs/REQUIREMENTS.md | REQ-### with acceptance criteria |
| docs/ARCHITECTURE.md | Stack, layout, contracts |
| docs/DECISIONS.md | Decisions and assumptions |
| docs/exec-plans/ | Phase plans |
| feature_list.json | Features F-001..F-019 |
| plan/ | Intake artifacts; 03-architecture.html is the interactive diagram |

## Commands
- Tests: `uv run pytest` (offline), `uv run pytest -m live -n 0` (model server running)
- Model server: `uv run agent-lab model start|stop|status`
