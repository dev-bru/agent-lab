"""Check the local math and time tools through an MCP client."""

import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fastmcp import Client

from agent_lab import mcp_server

ROOT = Path(__file__).resolve().parents[1]


def call(name: str, arguments: dict | None = None, *, raise_on_error: bool = True):
    """Call one tool through an in-memory client."""
    async def run():
        async with Client(mcp_server.mcp) as client:
            return await client.call_tool(name, arguments or {}, raise_on_error=raise_on_error)

    return asyncio.run(run())


def test_tool_names() -> None:
    """List all five tool names."""
    async def run():
        async with Client(mcp_server.mcp) as client:
            return {tool.name for tool in await client.list_tools()}

    assert {"add", "multiply", "convert_units", "now", "days_between"} <= asyncio.run(run())


def test_math() -> None:
    """Check positive, fractional, and zero results."""
    assert call("multiply", {"a": 17, "b": 23}).data == 391
    assert call("add", {"a": 2, "b": 3.5}).data == 5.5
    assert call("multiply", {"a": -2, "b": 0}).data == 0


def test_conversions() -> None:
    """Check length, mass, temperature, and matching units."""
    cases = [
        (1, "mi", "km", 1.609344),
        (0, "C", "F", 32),
        (32, "F", "C", 0),
        (100, "C", "K", 373.15),
        (0, "K", "C", -273.15),
        (1, "lb", "kg", 0.453592),
        (5, "m", "m", 5),
    ]
    for value, source, target, expected in cases:
        assert call("convert_units", {"value": value, "from_unit": source, "to_unit": target}).data == expected


def test_unit_errors() -> None:
    """Explain unknown units and incompatible unit kinds."""
    def error(source: str, target: str) -> str:
        result = call("convert_units", {"value": 1, "from_unit": source, "to_unit": target}, raise_on_error=False)
        assert result.is_error and result.data is None
        return result.content[0].text

    unknown = error("parsec", "m")
    assert "unknown unit 'parsec'" in unknown
    assert "mm, cm, m, km, in, ft, mi, g, kg, lb, C, F, K" in unknown
    mixed = error("km", "kg")
    assert "km (length)" in mixed and "kg (mass)" in mixed
    assert "mm, cm, m, km, in, ft, mi" in mixed
    assert "unknown unit 'KM'" in error("KM", "m")


def test_dates() -> None:
    """Count days in both directions and report invalid dates."""
    for start, end, expected in [
        ("2026-10-29", "2026-12-31", 63),
        ("2026-12-31", "2026-10-29", -63),
        ("2026-10-29", "2026-10-29", 0),
    ]:
        assert call("days_between", {"start": start, "end": end}).data == expected
    for bad in ("2026-02-30", "29-10-2026"):
        result = call("days_between", {"start": bad, "end": "2026-10-29"}, raise_on_error=False)
        assert result.is_error and result.data is None
        assert "YYYY-MM-DD" in result.content[0].text and bad in result.content[0].text


def test_time_zones() -> None:
    """Return parsed times and explain invalid zone names."""
    kolkata = call("now", {"timezone": "Asia/Kolkata"}).data
    assert kolkata.endswith("+05:30")
    datetime.fromisoformat(kolkata)
    assert call("now").data.endswith("+00:00")
    for bad in ("Mars/Base", "../x"):
        result = call("now", {"timezone": bad}, raise_on_error=False)
        assert result.is_error and result.data is None
        assert "IANA" in result.content[0].text


def test_source_is_local() -> None:
    """Keep network addresses out of the server source."""
    source = Path(mcp_server.__file__).read_text(encoding="utf-8")
    assert "http://" not in source and "https://" not in source


def test_main_starts_without_banner(monkeypatch) -> None:
    """Start the server with its banner disabled."""
    calls = []
    monkeypatch.setattr(mcp_server.mcp, "run", lambda **kwargs: calls.append(kwargs))
    mcp_server.main()
    assert calls == [{"show_banner": False}]


def test_update_check_is_off() -> None:
    """Keep the FastMCP update check disabled after import."""
    assert os.environ["FASTMCP_CHECK_FOR_UPDATES"] == "off"


def test_stdio_starts_locally() -> None:
    """Exit cleanly when standard input closes."""
    result = subprocess.run(
        [sys.executable, "-m", "agent_lab.mcp_server"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "FASTMCP_CHECK_FOR_UPDATES": "stable"},
        check=False,
    )
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    assert "http" not in result.stderr.lower()
