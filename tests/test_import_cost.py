"""Check that offline imports do not load real model libraries."""

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(code):
    """Run Python with the project source on its import path."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True,
        text=True, encoding="utf-8", timeout=60, check=True,
    )
    assert result.stdout.splitlines()[-2:] == ["False", "False"]


def test_offline_imports_do_not_load_litellm():
    """Import fake and graph modules without loading real model libraries."""
    _run("""import sys
import agent_lab.fakes, agent_lab.model, agent_lab.agent.graph
print('litellm' in sys.modules)
print('langchain_litellm' in sys.modules)
""")


def test_fake_lesson_does_not_load_litellm():
    """Run the first fake lesson without loading real model libraries."""
    _run("""import importlib.util
import sys
from pathlib import Path
path = Path('lessons/01_model_call.py')
spec = importlib.util.spec_from_file_location('lesson_01', path)
lesson = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lesson)
assert lesson.main(['--fake']) == 0
print('litellm' in sys.modules)
print('langchain_litellm' in sys.modules)
""")
