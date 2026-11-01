"""See how a model asks for a tool. Run the tool and send its answer back. Use --fake without a model server."""

import argparse
import json
import sys

from agent_lab import fakes, model, model_server, settings, tools_schema


MULTIPLY = {"type": "function", "function": {
    "name": "multiply",
    "description": "Multiply two numbers. Give a and b as numbers.",
    "parameters": {"type": "object", "properties": {
        "a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]},
}}


def multiply(a, b):
    """Multiply two numbers."""
    return a * b


def show(x):
    """Show a whole float without its decimal point."""
    return str(int(x)) if isinstance(x, float) and x.is_integer() else str(x)


def run(chat) -> int:
    """Show one tool request, its result, and the model's final answer."""
    try:
        # Give the model a question that asks for the tool.
        question = "What is 17 times 23? Use the multiply tool."
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Use tools when they help."},
            {"role": "user", "content": question},
        ]
        print(f"you> {question}")

        # Offer the tool and read the model's first reply.
        reply = chat(messages, tools=[MULTIPLY])

        # Stop if the model answered without asking for a tool.
        if not reply.tool_calls:
            print(f"agent> {reply.text}")
            print("the model answered without a tool")
            return 0

        # Keep the tool request and its ids in the conversation.
        messages.append({"role": "assistant", "content": reply.text or "", "tool_calls": [
            {"id": call.id, "type": "function", "function": {
                "name": call.name, "arguments": call.arguments}} for call in reply.tool_calls]})

        # Answer each tool request with its matching id.
        for call in reply.tool_calls:
            print(f"agent> tool call {call.name} {call.arguments}")
            try:
                args = json.loads(call.arguments)
            except (json.JSONDecodeError, TypeError):
                problems = ["arguments are not valid JSON"]
            else:
                if call.name != "multiply":
                    problems = [f"unknown tool '{call.name}'; valid tools: multiply"]
                else:
                    problems = tools_schema.check_args(MULTIPLY["function"]["parameters"], args)

            if problems:
                content = f"error: {'; '.join(problems)}"
            else:
                content = show(multiply(**args))
            print(f"[tool: {call.name}] {content}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

        # Give all tool results to the model for its final reply.
        final = chat(messages, tools=[MULTIPLY])
        print(f"agent> {final.text}")
        if final.tool_calls:
            print("the model asked for another tool; this lesson stops here")
    except fakes.ScriptExhausted:
        print("error: the fake script has no more replies", file=sys.stderr)
        return 1
    except (model.ModelError, model_server.ModelServerError, settings.SettingsError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def main(argv=None) -> int:
    """Choose a fake script or the local model, then run the lesson."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake", nargs="?", const=fakes.builtin("02_tool_call"), default=None,
                        metavar="SCRIPT", help="Use the built-in or a given fake script.")
    args = parser.parse_args(argv)
    try:
        chat = fakes.FakeModel(args.fake).chat if args.fake is not None else model.chat
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return run(chat)


if __name__ == "__main__":
    raise SystemExit(main())
