"""Run the local agent with LangGraph.

LangGraph writes its own unknown-tool text, unlike hand.
Invalid JSON arguments from a real model end the run.
The trace stores json.dumps(args) instead of the model's raw argument string.
Its model_request has only step, and tool_result is_error comes from the ToolMessage, not the MCP flag.
"""

import json
from typing import TYPE_CHECKING
from urllib.parse import urlunsplit

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.errors import GraphRecursionError
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

# Importing model sets LiteLLM's local settings (no proxy for localhost), so keep it.
from agent_lab import model as model_module, settings, tools_schema  # noqa: F401
from agent_lab.agent import LIMIT_MESSAGE, SYSTEM_PROMPT, RunResult
from agent_lab.mcp_client import McpTools

if TYPE_CHECKING:
    from langchain_litellm import ChatLiteLLM


def chat_model(config=None) -> "ChatLiteLLM":
    """Make a LangChain model for the local model server."""
    from langchain_litellm import ChatLiteLLM
    import litellm

    litellm.suppress_debug_info = True
    config = config or settings.load()
    # Use the same endpoint and thinking setting as the hand agent.
    return ChatLiteLLM(
        model=f"openai/{config.model_name}",
        api_base=urlunsplit(("http", f"{config.host}:{config.port}", "/v1", "", "")),
        request_timeout=config.timeout_s,
        max_retries=0,
        model_kwargs={"api_key": "local", "extra_body": {"chat_template_kwargs": {
            "enable_thinking": False}}},
    )


def as_langchain_tools(mcp_tools: McpTools) -> list[StructuredTool]:
    """Wrap each MCP tool for LangGraph and check its arguments."""
    def make_tool(name, schema):
        """Bind one tool name and schema before the loop moves on."""
        def call(**args):
            """Check one request and return its MCP result as text."""
            problems = tools_schema.check_args(schema, args)
            if problems:
                return "error: " + "; ".join(problems)
            text, is_error = mcp_tools.call(name, args)
            return "error: " + text if is_error else text

        return call

    # A dict schema needs this explicit check in the wrapped function.
    return [StructuredTool.from_function(
        func=make_tool(spec["function"]["name"], spec["function"]["parameters"]),
        name=spec["function"]["name"],
        description=spec["function"]["description"],
        args_schema=spec["function"]["parameters"],
    ) for spec in mcp_tools.specs()]


def build(chat_model, tools):
    """Compile the model and tool loop."""
    bound = chat_model.bind_tools(tools)

    def model_node(state):
        """Ask the bound model for the next message."""
        return {"messages": [bound.invoke(state["messages"])]}

    # ponytail: Invalid JSON tool calls end the run; handle them if real models need repair.
    # The condition sends valid tool calls to ToolNode and a final reply to END.
    graph = StateGraph(MessagesState)
    graph.add_node("model", model_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", tools_condition)
    graph.add_edge("tools", "model")
    return graph.compile()


def run(question, *, model, tools: McpTools, trace=None, max_steps=6, echo=None) -> RunResult:
    """Stream the graph and record the same event kinds as the hand agent."""
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")
    if trace:
        trace.write("user", text=question)
    steps = 0
    answer = ""
    calls = []
    try:
        # Each model and tool update becomes one learner-visible event.
        graph = build(model, as_langchain_tools(tools))
        inputs = {"messages": [SystemMessage(SYSTEM_PROMPT), HumanMessage(question)]}
        for update in graph.stream(inputs, {"recursion_limit": 2 * max_steps},
                                   stream_mode="updates"):
            for node, data in update.items():
                if echo:
                    echo(f"[node: {node}]")
                if node == "model":
                    steps += 1
                    message = data["messages"][0]
                    answer = message.content if isinstance(message.content, str) else ""
                    calls = [{"id": call["id"], "name": call["name"],
                              "arguments": json.dumps(call["args"])}
                             for call in message.tool_calls]
                    if trace:
                        trace.write("model_request", step=steps)
                        trace.write("model_reply", text=answer, tool_calls=calls)
                    if not calls and trace:
                        trace.write("final", text=answer)
                elif node == "tools":
                    # ToolNode returns results in call order with matching IDs.
                    for message in data["messages"]:
                        call = next(call for call in calls if call["id"] == message.tool_call_id)
                        content = message.content
                        # Our adapter puts MCP errors in text, so status alone is not enough.
                        is_error = message.status == "error" or content.startswith("error: ")
                        if trace:
                            trace.write("tool_call", **call)
                            trace.write("tool_result", id=call["id"], name=call["name"],
                                        content=content, is_error=is_error)
                        if echo:
                            echo(f"[tool: {call['name']}] {content}")
    except GraphRecursionError:
        if trace:
            trace.write("limit", steps=max_steps)
        return RunResult(LIMIT_MESSAGE.format(max_steps), max_steps, "limit")
    except Exception as error:
        mapped = model_module.model_error(error)
        if trace:
            trace.write("error", message=str(mapped if mapped is not None else error))
        if mapped is not None:
            raise mapped from error
        raise
    return RunResult(answer, steps, "answer")
