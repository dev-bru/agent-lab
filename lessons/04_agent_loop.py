"""Watch the hand-written agent solve a task. See each step and tool result. Find the saved trace."""

import argparse
import sys

from agent_lab import fakes, mcp_client, model, model_server, settings, trace
from agent_lab.agent import hand


QUESTION = "What is 17 times 23? Save the answer as a note called result."


def run(chat_model) -> int:
    """Run the agent and show its answer and trace path."""
    try:
        # Step 1: Load local folders and show the question.
        config = settings.load()
        print(f"you> {QUESTION}")

        # Step 2: Open the local tools and a trace file.
        with mcp_client.McpTools(settings=config) as tools, trace.Trace.new(config.runs_dir, "hand") as log:
            # Step 3: Let the agent ask the model and use tools.
            result = hand.run(QUESTION, model=chat_model, tools=tools, trace=log, echo=print)

            # Step 4: Show the answer and where the trace was saved.
            print(f"agent> {result.text}")
            print(f"[trace] {log.path}")

            # Step 5: Report whether the agent answered.
            return 0 if result.stopped_by == "answer" else 1
    except fakes.ScriptExhausted:
        print("error: the fake script has no more replies", file=sys.stderr)
        return 1
    except (model.ModelError, model_server.ModelServerError, settings.SettingsError,
            mcp_client.McpError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def main(argv=None) -> int:
    """Choose a fake script or the local model, then run the lesson."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake", nargs="?", const=fakes.builtin("two_tool"), default=None,
                        metavar="SCRIPT", help="Use the built-in or a given fake script.")
    args = parser.parse_args(argv)
    try:
        chat_model = fakes.FakeModel(args.fake) if args.fake is not None else model
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return run(chat_model)


if __name__ == "__main__":
    raise SystemExit(main())
