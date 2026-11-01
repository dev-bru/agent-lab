"""Offer local math, unit, date, time, note, and docs tools to the agent."""

import os
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agent_lab import settings

os.environ["FASTMCP_CHECK_FOR_UPDATES"] = "off"

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError


mcp = FastMCP("agent-lab")

UNITS = {
    "length": {"mm": 0.001, "cm": 0.01, "m": 1, "km": 1000, "in": 0.0254, "ft": 0.3048, "mi": 1609.344},
    "mass": {"g": 0.001, "kg": 1, "lb": 0.45359237},
    "temperature": {"C": 1, "F": 1, "K": 1},
}
ALL_UNITS = ", ".join(unit for kind in UNITS.values() for unit in kind)


def _notes_dir() -> Path:
    """Read the notes folder from current settings."""
    try:
        return Path(settings.load().notes_dir)
    except settings.SettingsError as error:
        raise ToolError(str(error)) from None


def _docs_dir() -> Path:
    """Read the docs folder from current settings."""
    try:
        return Path(settings.load().docs_dir)
    except settings.SettingsError as error:
        raise ToolError(str(error)) from None


def _valid_name(name: str) -> bool:
    """Check that a name is safe for a local file."""
    devices = {"CON", "PRN", "AUX", "NUL"}
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name, re.ASCII)) and not (
        name.upper() in devices or re.fullmatch(r"(?:COM|LPT)[1-9]", name.upper())
    )


def _note_path(name: str) -> Path:
    """Check a note name and keep its path inside the notes folder."""
    if not _valid_name(name):
        raise ToolError(
            "note names use 1 to 64 letters, digits, _ or -, and not a device name such as CON; "
            f"got '{name}'"
        )
    base = _notes_dir().resolve()
    path = base / f"{name}.md"
    if not path.resolve().is_relative_to(base):
        raise ToolError("note path is outside the notes folder")
    return path


@mcp.tool
def add(a: float, b: float) -> float:
    """Add two numbers. Give a and b as numbers."""
    return a + b


@mcp.tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers. Give a and b as numbers."""
    return a * b


@mcp.tool
def convert_units(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a number between units. Give value, from_unit, and to_unit using exact unit names."""
    kinds = {}
    for unit in (from_unit, to_unit):
        kind = next((name for name, units in UNITS.items() if unit in units), None)
        if kind is None:
            raise ToolError(f"unknown unit '{unit}'; valid units: {ALL_UNITS}")
        kinds[unit] = kind

    source_kind = kinds[from_unit]
    target_kind = kinds[to_unit]
    if source_kind != target_kind:
        valid = ", ".join(UNITS[source_kind])
        raise ToolError(
            f"cannot convert {from_unit} ({source_kind}) to {to_unit} ({target_kind}); "
            f"valid {source_kind} units: {valid}"
        )

    if source_kind == "temperature":
        base = value if from_unit == "C" else (value - 32) * 5 / 9 if from_unit == "F" else value - 273.15
        result = base if to_unit == "C" else base * 9 / 5 + 32 if to_unit == "F" else base + 273.15
    else:
        result = value * UNITS[source_kind][from_unit] / UNITS[source_kind][to_unit]
    return round(result, 6)


@mcp.tool
def now(timezone: str = "UTC") -> str:
    """Get the current time. Give timezone as an IANA name, or omit it for UTC."""
    try:
        return datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds")
    except (ZoneInfoNotFoundError, ValueError):
        raise ToolError(f"unknown time zone '{timezone}'; use an IANA name such as Asia/Kolkata or UTC") from None


@mcp.tool
def days_between(start: str, end: str) -> int:
    """Count days from start to end. Give each date as YYYY-MM-DD."""
    dates = []
    for value in (start, end):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value, re.ASCII):
            raise ToolError(f"dates must be YYYY-MM-DD, got '{value}'")
        try:
            dates.append(date.fromisoformat(value))
        except ValueError:
            raise ToolError(f"dates must be YYYY-MM-DD, got '{value}'") from None
    return (dates[1] - dates[0]).days


@mcp.tool
def write_note(name: str, text: str) -> str:
    """Save a note. Give name (letters, digits, _ or -, up to 64) and text (up to 10000 characters)."""
    try:
        path = _note_path(name)
        if len(text) > 10000:
            raise ToolError(f"note text is longer than 10000 characters ({len(text)})")
        try:
            text.encode("utf-8")
        except UnicodeEncodeError:
            raise ToolError(f"cannot write note '{name}': text is not valid UTF-8") from None
        # ponytail: Another process can swap this entry after the check; these tools never create links.
        existed = path.exists()
        if existed and os.stat(path).st_nlink > 1:
            raise ToolError(f"cannot write note '{name}': it is linked to another file")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as file:
            file.write(text)
    except OSError as error:
        raise ToolError(f"cannot write note '{name}': {error.strerror or type(error).__name__}") from None
    return f"{'updated' if existed else 'saved'} note '{name}'"


@mcp.tool
def read_note(name: str) -> str:
    """Read a saved note by name. Use list_notes to see the names."""
    try:
        path = _note_path(name)
        with open(path, encoding="utf-8", newline="") as file:
            return file.read()
    except FileNotFoundError:
        raise ToolError(f"no note named '{name}'; use list_notes to see the names") from None
    except (OSError, UnicodeError) as error:
        reason = error.strerror or type(error).__name__ if isinstance(error, OSError) else str(error)
        raise ToolError(f"cannot read note '{name}': {reason}") from None


@mcp.tool
def list_notes() -> list[str]:
    """List the names of saved notes."""
    base = _notes_dir().resolve()
    if not base.exists():
        return []
    return sorted(
        path.stem for path in base.glob("*.md")
        if path.is_file()
        and path.resolve().is_relative_to(base)
        and _valid_name(path.stem)
    )


@mcp.tool
def search_docs(query: str, limit: int = 3) -> list[dict]:
    """Search the local docs for words. Give query words and limit from 1 to 10."""
    words = set(re.findall(r"[a-z0-9]+", query.lower(), re.ASCII))
    if not words:
        raise ToolError("query needs at least one word")
    if not 1 <= limit <= 10:
        raise ToolError(f"limit must be from 1 to 10, got {limit}")

    base = _docs_dir().resolve()
    if not base.is_dir():
        return []

    matches = []
    for path in base.glob("*.md"):
        if not path.is_file() or not path.resolve().is_relative_to(base):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace", newline="") as file:
                lines = file.read().split("\n")
        except OSError:
            continue

        score = 0
        best_hits = 0
        best_line = 0
        best_text = ""
        for number, raw_line in enumerate(lines, 1):
            line = raw_line.removesuffix("\r")
            hits = sum(word in words for word in re.findall(r"[a-z0-9]+", line.lower(), re.ASCII))
            score += hits
            if hits > best_hits:
                best_hits = hits
                best_line = number
                best_text = line.strip()[:300]
        if score:
            matches.append((score, path.name, best_line, best_text))

    matches.sort(key=lambda item: (-item[0], item[1]))
    return [{"file": name, "line": number, "text": text}
            for _, name, number, text in matches[:limit]]


@mcp.resource("docs://{name}")
def read_doc(name: str) -> str:
    """Read one local Markdown doc by name."""
    if not _valid_name(name):
        raise ResourceError("doc names use 1 to 64 letters, digits, _ or -, and not a device name such as CON; "
                            f"got '{name}'")
    try:
        base = _docs_dir().resolve()
        path = base / f"{name}.md"
        if not path.resolve().is_relative_to(base):
            raise ResourceError("doc path is outside the docs folder")
        with open(path, encoding="utf-8", newline="") as file:
            return file.read()
    except FileNotFoundError:
        raise ResourceError(f"no doc named '{name}'") from None
    except (OSError, UnicodeError) as error:
        raise ResourceError(f"cannot read doc '{name}': {error}") from None


@mcp.prompt
async def explain_tool(tool_name: str) -> str:
    """Ask for a beginner explanation of a tool."""
    tools = await mcp.list_tools()
    tool = next((item for item in tools if item.name == tool_name), None)
    if tool is None:
        raise ValueError(f"unknown tool '{tool_name}'; valid tools: {', '.join(item.name for item in tools)}")
    return f"Explain the {tool.name} tool to a beginner in plain words. Its description is: {tool.description}"


def main() -> None:
    """Run the local MCP server on standard input and output."""
    mcp.run(show_banner=False)


if __name__ == "__main__":
    main()
