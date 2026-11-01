"""Call the local MCP server from ordinary synchronous code."""

import asyncio
import json
import os
import sys
import threading
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from agent_lab import settings as settings_module, tools_schema


class McpError(RuntimeError):
    """Report a failed MCP session or tool call."""


class McpTools:
    """Keep one local MCP child open for synchronous tool calls."""

    def __init__(self, module="agent_lab.mcp_server", settings=None):
        """Save the server module and the local folder settings."""
        self.module = module
        self.settings = settings if settings is not None else settings_module.load()
        self._ready = threading.Event()
        self._closed = False
        self._thread = None
        self._loop = None
        self._stop = None
        self._client = None
        self._tools = []
        self._specs = []
        self._error = None

    async def _main(self):
        """Enter and leave the client in the same task."""
        try:
            self._loop = asyncio.get_running_loop()
            self._stop = asyncio.Event()
            if self._closed:
                self._stop.set()
            env = {**os.environ,
                   "AGENT_LAB_NOTES_DIR": str(Path(self.settings.notes_dir).resolve()),
                   "AGENT_LAB_DOCS_DIR": str(Path(self.settings.docs_dir).resolve())}
            transport = StdioTransport(command=sys.executable, args=["-m", self.module],
                                       env=env, cwd=os.getcwd(), keep_alive=False,
                                       log_file=Path(os.devnull))
            async with Client(transport, mode="legacy") as client:
                self._client = client
                self._tools = await client.list_tools()
                self._specs = [tools_schema.to_openai(tool) for tool in self._tools]
                self._ready.set()
                await self._stop.wait()
        except Exception as error:
            self._error = error
            self._ready.set()

    def open(self):
        """Start the MCP child and wait until its tools are ready."""
        if self._closed:
            raise McpError("session is closed")
        if self._thread is not None:
            return self
        self._thread = threading.Thread(target=lambda: asyncio.run(self._main()), daemon=True)
        self._thread.start()
        try:
            ready = self._ready.wait(self.settings.timeout_s)
        except BaseException:
            try:
                self.close()
            except McpError:
                pass
            raise
        if not ready or self._error is not None:
            reason = str(self._error) if self._error is not None else "timed out"
            try:
                self.close()
            except McpError as error:
                reason = f"{reason}; {error}"
            raise McpError(f"MCP server did not start: {reason}") from self._error
        return self

    def specs(self) -> list[dict]:
        """Return the one list of tool definitions offered to the model."""
        return self._specs

    def schema(self, name):
        """Return a tool's input rules, or None for an unknown tool."""
        return next((tool.input_schema for tool in self._tools if tool.name == name), None)

    def names(self):
        """Return the available tool names in sorted order."""
        return sorted(tool.name for tool in self._tools)

    def call(self, name, args) -> tuple[str, bool]:
        """Call one tool and return its text and error flag."""
        if self._closed or self._thread is None:
            raise McpError("session is closed")
        if not self._thread.is_alive():
            raise McpError(f"tool call failed: {self._error or 'session stopped'}")
        future = None
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._client.call_tool(name, args, raise_on_error=False,
                                       timeout=self.settings.timeout_s), self._loop)
            result = future.result(timeout=self.settings.timeout_s + 5)
        except BaseException as error:
            if future is not None:
                future.cancel()
            if not isinstance(error, Exception):
                raise
            raise McpError(f"tool call failed: {error}") from error
        result_text = "\n".join(item.text for item in result.content if hasattr(item, "text"))
        if not result_text and result.structured_content is not None:
            data = result.structured_content
            # ponytail: FastMCP wraps list results in "result"; unwrap only that single field.
            if isinstance(data, dict) and set(data) == {"result"}:
                data = data["result"]
            result_text = json.dumps(data)
        return result_text, bool(result.is_error)

    def close(self):
        """Stop the MCP child and wait for its owner thread."""
        if self._closed:
            return
        self._closed = True
        if self._loop is not None and self._stop is not None and self._thread.is_alive():
            self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread is not None:
            self._thread.join(10)
            if self._thread.is_alive():
                raise McpError("MCP server did not stop")

    def __enter__(self):
        """Open the local MCP session for a with block."""
        return self.open()

    def __exit__(self, _type, _value, _traceback):
        """Close the local MCP session after a with block."""
        self.close()
