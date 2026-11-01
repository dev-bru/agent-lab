"""Start a local MCP server and ask what it offers. Call one tool. Read a resource when available."""

import argparse
import asyncio
import os
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def run(module: str) -> int:
    """Show the server details, its tools, one result, and an optional resource."""
    try:
        # Start the server in a child process and connect over standard input and output.
        transport = StdioTransport(
            command=sys.executable, args=["-m", module],
            env={**os.environ}, cwd=os.getcwd(), keep_alive=False,
        )
        # "legacy" uses the classic MCP start: the client sends initialize first, as the steps below show.
        async with Client(transport, mode="legacy") as client:
            # Show the server name and version from the first MCP reply.
            info = client.initialize_result.server_info
            print(f"server: {info.name} {info.version}", flush=True)

            # Ask the server which tools it offers.
            tools = await client.list_tools()
            print(f"tools: {len(tools)}", flush=True)
            for tool in sorted(tools, key=lambda item: item.name):
                print(f"- {tool.name}: {tool.description.splitlines()[0]}", flush=True)

            # Call a tool with named inputs and show its result.
            result = await client.call_tool("multiply", {"a": 17, "b": 23})
            print(f"[tool: multiply] 17 x 23 = {result.data:g}", flush=True)

            # Ask for resources and read the teaching document if it is offered.
            resources = await client.list_resources()
            if not resources:
                print("no resources offered", flush=True)
            elif not any(str(resource.uri) == "docs://mcp-basics" for resource in resources):
                print("resource docs://mcp-basics not offered", flush=True)
            else:
                contents = await client.read_resource("docs://mcp-basics")
                print("resource docs://mcp-basics:", flush=True)
                print(contents[0].text, flush=True)
    except Exception as error:
        print(f"error: {type(error).__name__}: {str(error) or 'server did not start'}", file=sys.stderr)
        return 1
    return 0


def main(argv=None) -> int:
    """Read the server module option and run the lesson."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="agent_lab.mcp_server", metavar="MODULE")
    args = parser.parse_args(argv)
    return asyncio.run(run(args.server))


if __name__ == "__main__":
    raise SystemExit(main())
