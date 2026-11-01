"""Load Agent Lab settings from a file and environment variables."""

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Mapping


class SettingsError(ValueError):
    """A settings value is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    """Store the settings used by Agent Lab."""

    llama_server: str = "llama-server.exe"
    model: str = "models/Qwen3-1.7B-Q8_0.gguf"
    host: str = "127.0.0.1"
    port: int = 8090
    model_name: str = "qwen3-1.7b"
    max_steps: int = 6
    timeout_s: int = 120
    notes_dir: str = "sandbox/notes"
    docs_dir: str = "docs_corpus"
    runs_dir: str = "runs"


def load(path: Path | None = None, env: Mapping[str, str] | None = None) -> Settings:
    """Read the settings file, then apply environment values."""

    path = Path("agent-lab.toml") if path is None else path
    env = os.environ if env is None else env
    values = {}
    if path.exists():
        try:
            with path.open("rb") as file:
                values = tomllib.load(file)
        except tomllib.TOMLDecodeError as error:
            raise SettingsError(f"Invalid TOML in {path}: {error}") from error

    known = {field.name: field.type for field in fields(Settings)}
    for key in values:
        if key not in known:
            raise SettingsError(f"Unknown setting: {key}")

    for key, kind in known.items():
        override = env.get(f"AGENT_LAB_{key.upper()}")
        if override:
            values[key] = override
        if key not in values:
            continue
        value = values[key]
        if kind is int:
            try:
                values[key] = int(value)
            except (TypeError, ValueError) as error:
                raise SettingsError(f"{key} must be an integer, got {value!r}") from error
        elif not isinstance(value, str):
            raise SettingsError(f"{key} must be a string, got {value!r}")
    return Settings(**values)
