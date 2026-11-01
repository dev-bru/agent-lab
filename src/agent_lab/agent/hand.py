"""Run a simple agent loop through the local model and MCP tools."""

import json
from typing import Callable

from agent_lab import model as model_module, tools_schema
from agent_lab.agent import LIMIT_MESSAGE, SYSTEM_PROMPT, RunResult


def run(question, *, model, tools, trace=None, max_steps=6,
        echo: Callable[[str], None] | None = None) -> RunResult:
    """Ask the model, run its tools, and stop on an answer or step limit."""
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")
    history = [{"role": "system", "content": SYSTEM_PROMPT},
               {"role": "user", "content": question}]
    if trace:
        trace.write("user", text=question)

    for step in range(1, max_steps + 1):
        # Show where the learner is in the loop.
        if echo:
            echo(f"[step {step}/{max_steps}]")
        if trace:
            trace.write("model_request", step=step, messages=len(history))
        # Ask the model for the next action.
        try:
            reply = model.chat(history, tools=tools.specs())
        except model_module.ModelError as error:
            if trace:
                trace.write("error", message=str(error))
            raise
        calls = [{"id": call.id, "name": call.name, "arguments": call.arguments}
                 for call in reply.tool_calls]
        if trace:
            trace.write("model_reply", text=reply.text, tool_calls=calls)
        if not calls:
            if trace:
                trace.write("final", text=reply.text or "")
            return RunResult(reply.text or "", step, "answer")

        # Keep the model's tool requests in the conversation.
        history.append({"role": "assistant", "content": reply.text or "",
                        "tool_calls": [{"id": call["id"], "type": "function",
                                        "function": {"name": call["name"],
                                                     "arguments": call["arguments"]}}
                                       for call in calls]})
        for call in calls:
            name, raw, call_id = call["name"], call["arguments"], call["id"]
            if trace:
                trace.write("tool_call", id=call_id, name=name, arguments=raw)
            # Check arguments before asking the MCP server to run a tool.
            try:
                args = json.loads(raw) if raw.strip() else {}
                problems = []
            except (json.JSONDecodeError, AttributeError, TypeError):
                args = None
                problems = ["arguments are not valid JSON"]
            if not problems:
                schema = tools.schema(name)
                if schema is None:
                    problems = [f"unknown tool '{name}'; valid tools: {', '.join(tools.names())}"]
                else:
                    problems = tools_schema.check_args(schema, args)
            if problems:
                content, is_error = "error: " + "; ".join(problems), True
            else:
                text, is_error = tools.call(name, args)
                content = "error: " + text if is_error else text
            # Give each result to the model in the next request.
            if trace:
                trace.write("tool_result", id=call_id, name=name, content=content, is_error=is_error)
            if echo:
                echo(f"[tool: {name}] {content}")
            history.append({"role": "tool", "tool_call_id": call_id, "content": content})

    # The final allowed tool call has run, but no model answer followed it.
    if trace:
        trace.write("limit", steps=max_steps)
    return RunResult(LIMIT_MESSAGE.format(max_steps), max_steps, "limit")
