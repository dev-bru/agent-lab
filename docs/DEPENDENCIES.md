# Agent Lab: dependencies

Every dependency, pinned. Installed 2026-10-31 with the human's approval (D-012). Exact hashes for every package,
including the 129 resolved transitive ones, are in `uv.lock`. Labels: MEASURED (on this PC), DOCUMENTED (URL,
accessed 2026-10-31).

## Python packages (direct)
| Package | Version | Licence | Why | Source |
|---|---|---|---|---|
| fastmcp | 4.1.4 | Apache-2.0 | MCP tool server and client | DOCUMENTED https://pypi.org/pypi/fastmcp/json |
| litellm | 1.106.6 | MIT | One API for every model provider | DOCUMENTED https://pypi.org/pypi/litellm/json |
| langgraph | 1.2.18 | MIT | Graph agent (lesson 06) | DOCUMENTED https://pypi.org/pypi/langgraph/json |
| langchain-litellm | 0.11.2 | MIT | `ChatLiteLLM` model for LangGraph | DOCUMENTED https://pypi.org/pypi/langchain-litellm/json |
| pydantic | 2.14.2 | MIT | Structured output models (lesson 03) | DOCUMENTED https://pypi.org/pypi/pydantic/json |
| tzdata | 2026.6 | Apache-2.0 | Time-zone data for `zoneinfo` (Windows has none) | DOCUMENTED https://pypi.org/pypi/tzdata/json |
| pytest (dev) | 9.2.0 | MIT | Tests | DOCUMENTED https://pypi.org/pypi/pytest/json |
| pytest-xdist (dev) | 3.8.0 | MIT | Runs the offline tests in parallel (REQ-050); pulls in execnet 2.1.2 (MIT). Human approved 2026-10-31 (D-014) | DOCUMENTED https://pypi.org/pypi/pytest-xdist/json |
| playwright (dev) | 1.64.1 | Apache-2.0 | Trace viewer test, uses the installed Chrome (no browser download) | DOCUMENTED https://pypi.org/pypi/playwright/json |

Notable resolved packages (MEASURED with `uv tree`): mcp 2.3.0, langchain-core 1.7.3.

Removed before install: langchain-mcp-adapters 0.3.2. It needs `mcp<2`, but FastMCP 4.1.4 needs `mcp>=2.3`
(MEASURED with `uv lock`). Replaced by our own small adapter (D-012).

Supply chain: litellm 1.82.7 and 1.82.8 were compromised releases. langchain-litellm's own requirements exclude
them (DOCUMENTED in the requires_dist of https://pypi.org/pypi/langchain-litellm/0.8.1/json). Our pin, 1.106.6, is
not affected.

## Runtime tools (not installed by this project)
| Tool | Version | Where | Notes |
|---|---|---|---|
| Python | 3.12.15 | managed by uv | MEASURED (`uv python find 3.12`) |
| uv | 0.12.23 | WinGet | MEASURED |
| llama.cpp `llama-server` | 0.5.0-dev, build 11408, commit 9f12cd4a4, CUDA | any folder (path set in `agent-lab.toml`) | MEASURED (`--version`) |
| Google Chrome | 156.0.8078.74 | system install | MEASURED. Playwright uses `channel="chrome"` (A-2) |

## Model
| File | Source | Commit | Licence | Size | SHA-256 |
|---|---|---|---|---|---|
| Qwen3-1.7B-Q8_0.gguf | Qwen/Qwen3-1.7B-GGUF (Hugging Face) | 90862c4b9d2787eaed51d12237eafdfe7c5f6077 | Apache-2.0 | 1,834,426,016 bytes | 061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a |

MEASURED 2026-10-29: the SHA-256 matches the published value. The file stays in the shared models folder (A-3);
`agent-lab.toml` points to it.
