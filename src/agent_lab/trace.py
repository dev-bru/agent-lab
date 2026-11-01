"""Write each agent step as one line of local JSON."""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path


KINDS = ("user", "model_request", "model_reply", "tool_call", "tool_result", "error", "final", "limit")


class Trace:
    """Append readable agent events to one run file."""

    def __init__(self, path):
        """Open a trace file and start its elapsed clock."""
        self.path = Path(path)
        self._file = self.path.open("a", encoding="utf-8", errors="backslashreplace", newline="\n")
        self._start = time.monotonic()

    @classmethod
    def new(cls, runs_dir, engine):
        """Claim a new UTC run name, adding a number on collisions."""
        if re.fullmatch(r"[a-z]+", engine) is None:
            raise ValueError("engine must use lowercase letters")
        folder = Path(runs_dir)
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")[:-3]
        number = 1
        while True:
            suffix = "" if number == 1 else f"-{number}"
            path = folder / f"{stamp}-{engine}{suffix}.jsonl"
            try:
                with path.open("x", encoding="utf-8"):
                    pass
                return cls(path)
            except FileExistsError:
                number += 1

    def write(self, kind, **fields):
        """Write and flush one event with elapsed seconds."""
        if kind not in KINDS:
            raise ValueError(f"unknown trace kind: {kind}")
        record = {"t": round(time.monotonic() - self._start, 3), "kind": kind, **fields}
        self._file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self._file.flush()

    def close(self):
        """Close the run file."""
        self._file.close()

    def __enter__(self):
        """Return this trace for a with block."""
        return self

    def __exit__(self, _type, _value, _traceback):
        """Close the trace after a with block."""
        self.close()
