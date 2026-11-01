"""Check that shipped code uses local network addresses only."""

import ast
import re
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
URL = re.compile(r"https?://[^\s\"'<>]+")


def remote_urls(text: str, suffix: str) -> list[tuple[int, str]]:
    """Find remote URLs outside Python docstrings and allowed comments."""
    ignored: list[tuple[int, int]] = []
    if suffix == ".py":
        starts = [0]
        for line in text.splitlines(keepends=True):
            starts.append(starts[-1] + len(line))
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.body and isinstance(node.body[0], ast.Expr):
                    value = node.body[0].value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        ignored.append((starts[value.lineno - 1] + value.col_offset,
                                        starts[value.end_lineno - 1] + value.end_col_offset))
    else:
        ignored = [(match.start(), match.end()) for match in re.finditer(r"<!--.*?-->", text, re.DOTALL)]

    found = []
    for match in URL.finditer(text):
        if urlsplit(match.group()).hostname in {"127.0.0.1", "localhost"}:
            continue
        if any(start <= match.start() < end for start, end in ignored):
            continue
        line_number = text.count("\n", 0, match.start()) + 1
        if suffix == ".py" and text.splitlines()[line_number - 1].lstrip().startswith("#"):
            continue
        found.append((line_number, match.group()))
    return found


def test_source_has_no_remote_urls() -> None:
    """List each remote URL found in shipped Python and the viewer."""
    paths = [*ROOT.joinpath("src").rglob("*.py"), *ROOT.joinpath("lessons").rglob("*.py"),
             ROOT / "viewer" / "viewer.html"]
    failures = [f"{path.relative_to(ROOT)}:{line}: {url}"
                for path in paths
                for line, url in remote_urls(path.read_text(encoding="utf-8"), path.suffix)]
    assert not failures, "\n".join(failures)


def test_scanner_finds_only_remote_code_url() -> None:
    """Ignore a comment and local URL but find a remote code URL."""
    sample = '# https://comment.example/a\nremote = "https://remote.example/a"\nlocal = "http://localhost:8090"\n'
    assert remote_urls(sample, ".py") == [(2, "https://remote.example/a")]
