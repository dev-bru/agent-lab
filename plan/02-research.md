# Agent Lab: research

Status: draft (2026-10-29). Every claim is MEASURED (on this PC), DOCUMENTED (URL, accessed 2026-10-29) or
UNVERIFIED. Versions are the latest on PyPI on that date; the plan pins exact versions with hashes (uv lock).

## Libraries
| Package | Version | Licence | Python | Role | Source |
|---|---|---|---|---|---|
| fastmcp | 4.1.4 | Apache-2.0 | >=3.10 | MCP server (tool catalog), also has a client | DOCUMENTED https://pypi.org/pypi/fastmcp/json |
| litellm | 1.106.6 | MIT | >=3.10,<3.15 | One model API for every provider (lesson 01-04, hand agent) | DOCUMENTED https://pypi.org/pypi/litellm/json |
| langgraph | 1.2.18 | MIT | >=3.10 | Graph agent framework (lesson 06); needs langchain-core >=1.4.7,<2 | DOCUMENTED https://pypi.org/pypi/langgraph/json |
| langchain-mcp-adapters | 0.3.2 (2026-08-06) | MIT | >=3.10 | Turns MCP tools into LangChain tools for LangGraph; needs mcp >=1.24,<2 | DOCUMENTED https://pypi.org/pypi/langchain-mcp-adapters/json |
| langchain-litellm | 0.11.2 (2026-10-25) | MIT | >=3.11,<4 | `ChatLiteLLM` model for LangGraph, so both agents use LiteLLM; needs litellm >=1.106.2, !=1.107.0 | DOCUMENTED https://pypi.org/pypi/langchain-litellm/json |
| pytest | pin at plan time | MIT | | Tests | UNVERIFIED version |

Python 3.12 via uv (harness default; every package above supports it).

## Model and runtime
- Model: Qwen3 1.7B, `Qwen/Qwen3-1.7B-GGUF`, file `Qwen3-1.7B-Q8_0.gguf`, commit 90862c4b, Apache-2.0, 1.83 GB.
  MEASURED: SHA-256 matches; stored in a shared models folder.
- Runtime: llama.cpp `llama-server` from a local folder (build 11408, CUDA). MEASURED: with `--jinja` it returns
  OpenAI-style `tool_calls` (1.26 s for one call on the 4 GB GPU).
- Thinking mode: Qwen3 thinks by default; append `/no_think` to the user or system message to turn it off per turn
  (DOCUMENTED https://qwenlm.github.io/blog/qwen3/). MEASURED: `/no_think` gave a direct tool call.
  UNVERIFIED: the `chat_template_kwargs: {"enable_thinking": false}` request field on this llama.cpp build.
- Port 8090 for this project (the harness reserves 8080, 8081, 8083, 8084).

## How the pieces connect
- LiteLLM to llama-server: model `openai/<name>`, `api_base="http://127.0.0.1:8090/v1"` (the `/v1` matters), a
  placeholder `api_key` because the OpenAI client always sends one (DOCUMENTED
  https://docs.litellm.ai/docs/providers/openai_compatible). UNVERIFIED: that `tools` pass through unchanged on this
  path (LiteLLM passes OpenAI parameters for the openai provider; a live smoke test will prove it).
- Hand-written agent to MCP: the FastMCP client lists tools, converts their JSON schemas to OpenAI tool format, and
  calls `call_tool` when the model asks.
- LangGraph agent to MCP: `langchain-mcp-adapters` loads the same MCP server's tools; `ChatLiteLLM` is the model.
- Transport: stdio (the agent starts the MCP server as a child process). No network port for MCP.

## Prior art
- Qwen-Agent (Qwen's own framework) handles Qwen tool templates (DOCUMENTED, Qwen3 blog). Not used: the goal is to
  learn the general, provider-neutral way.
- OpenAI Agents SDK: simpler than LangGraph, less common for graph-shaped agents (considered in the brainstorm).

## Pitfalls
- Small models pick wrong tools or invent arguments: the agent loop validates arguments against the tool schema and
  feeds the error back to the model; a step limit stops endless loops.
- Structured output: ask for JSON matching a Pydantic model, validate, retry once with the error; llama-server's
  JSON-schema grammar can force valid JSON (UNVERIFIED on this build; the lesson shows both).
- Supply chain: LiteLLM had compromised PyPI releases in 2026 (UNVERIFIED from memory: versions 1.82.7 and 1.82.8,
  March 2026). Pin an exact, reviewed version with hashes in the uv lock file and log it in DEPENDENCIES.
- Windows: stdio MCP servers must be started with the venv's Python; paths with spaces need quoting.
- The GPU holds one model at a time: stop `llama-server` when idle (harness local-model rule).

## Cost
INR 0 per month: everything runs on this PC; no accounts, no API keys.
