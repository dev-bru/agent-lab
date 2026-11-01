"""Check plain-English docstrings across the package and lessons."""

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_docstrings() -> None:
    """Require public docstrings and short sentences in every docstring."""
    problems = []
    for folder in (ROOT / "src" / "agent_lab", ROOT / "lessons"):
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            relative = path.relative_to(ROOT).as_posix()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                name = "<module>" if isinstance(node, ast.Module) else node.name
                line = 1 if isinstance(node, ast.Module) else node.lineno
                doc = ast.get_docstring(node)
                if not doc and (isinstance(node, ast.Module) or not name.startswith("_")):
                    problems.append(f"{relative}:{line} {name}: missing docstring")
                if doc:
                    for sentence in re.split(r"[.!?](?:\s+|$)", doc):
                        if len(sentence.split()) > 20:
                            problems.append(f"{relative}:{line} {name}: sentence exceeds 20 words")
    assert not problems, "\n".join(problems)
