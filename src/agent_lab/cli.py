"""Show the Agent Lab commands."""

import argparse
import sys
from pathlib import Path

from agent_lab import fakes, mcp_client, model as model_module, model_server, settings, trace
from agent_lab.model_server import ModelServerError
from agent_lab.settings import SettingsError


def main(argv=None) -> int:
    """Read a command and run the local agent or model server."""

    parser = argparse.ArgumentParser(prog="agent-lab")
    commands = parser.add_subparsers(dest="command")
    chat_help = "Chat with the local model. Each line is a new agent run with no memory of earlier lines."
    chat = commands.add_parser("chat", help=chat_help, description=chat_help)
    chat.add_argument("--engine", choices=["hand", "graph"], default="hand")
    chat.add_argument("--fake", nargs="?", const=fakes.builtin("chat"))
    model = commands.add_parser("model", help="Control the local model server.")
    model.add_argument("action", choices=["start", "stop", "status"])
    args = parser.parse_args(argv)
    if args.command == "model":
        try:
            config = settings.load()
            return getattr(model_server, args.action)(config, home=Path(".agent-lab"))
        except (SettingsError, ModelServerError) as error:
            print(error, file=sys.stderr)
            return 1
    if args.command == "chat":
        # Load the agents only for chat: LangGraph is slow to import.
        from agent_lab.agent import graph, hand
        try:
            config = settings.load()
            if args.fake is None:
                model_server.check_host(config)
                # Fail before the slow tool start and LiteLLM import.
                if not model_server.port_in_use(config):
                    raise model_module.server_down(config)
            if args.engine == "hand":
                chat_model = fakes.FakeModel(args.fake) if args.fake is not None else model_module
                run = hand.run
            else:
                chat_model = fakes.FakeChatModel(args.fake) if args.fake is not None else graph.chat_model(config)
                run = graph.run
            with mcp_client.McpTools(settings=config) as tools:
                while True:
                    try:
                        line = input("you> ")
                    except EOFError:
                        break
                    # Windows PowerShell adds this mark when it pipes text.
                    line = line.lstrip("\ufeff").strip()
                    if not line:
                        continue
                    if line == "exit":
                        break
                    with trace.Trace.new(config.runs_dir, args.engine) as log:
                        result = run(line, model=chat_model, tools=tools, trace=log, echo=print)
                    print(f"agent> {result.text}")
                    print(f"[trace] {log.path}")
            return 0
        except model_module.ModelServerDown as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        except fakes.ScriptExhausted:
            print("error: the fake script has no more replies", file=sys.stderr)
            return 1
        except (model_module.ModelError, ModelServerError, SettingsError, mcp_client.McpError,
                OSError, ValueError, ImportError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print()
            return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
