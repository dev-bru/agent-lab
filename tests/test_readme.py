"""Check that the README covers each lesson and stays local."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_setup_has_short_numbered_list() -> None:
    """Keep the setup list between one and ten direct items."""
    setup = README.split("## Setup\n", 1)[1].split("\n## ", 1)[0]
    assert 1 <= len(re.findall(r"^\d+\. ", setup, re.MULTILINE)) <= 10


def test_each_lesson_has_matching_diagram_tab() -> None:
    """Map each numbered lesson to its matching diagram tab."""
    rows = [line for line in README.splitlines() if line.startswith("|")]
    for lesson in (ROOT / "lessons").glob("[0-9][0-9]_*.py"):
        matches = [row for row in rows if f"`lessons/{lesson.name}`" in row]
        assert len(matches) == 1, lesson.name
        assert re.search(rf"03-architecture\.html, tab {int(lesson.name[:2])}\b", matches[0]), lesson.name


def test_readme_has_no_urls() -> None:
    """Keep internet URLs out of the README."""
    assert "http://" not in README and "https://" not in README
