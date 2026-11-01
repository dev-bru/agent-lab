"""Check settings defaults, overrides, and errors."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from agent_lab.settings import Settings, SettingsError, load


def test_defaults(tmp_path: Path) -> None:
    """Use defaults when the file and environment values are absent."""

    assert load(tmp_path / "missing.toml", {}) == Settings()


def test_example_matches_defaults() -> None:
    """Keep the example file in step with the code defaults."""

    root = Path(__file__).resolve().parents[1]
    assert load(root / "agent-lab.example.toml", {}) == Settings()


def test_file_overrides_defaults(tmp_path: Path) -> None:
    """Read values from the settings file."""

    path = tmp_path / "agent-lab.toml"
    path.write_text('port = 9000\nmodel = "local.gguf"\n', encoding="utf-8")
    assert load(path, {}) == Settings(port=9000, model="local.gguf")


def test_environment_wins_over_file(tmp_path: Path) -> None:
    """Use the environment value after the file value."""

    path = tmp_path / "agent-lab.toml"
    path.write_text("port = 9000\n", encoding="utf-8")
    assert load(path, {"AGENT_LAB_PORT": "9999"}).port == 9999
    assert load(path, {"AGENT_LAB_PORT": ""}).port == 9000


@pytest.mark.parametrize("source", ["env", "file"])
def test_bad_integer_names_key(tmp_path: Path, source: str) -> None:
    """Name the setting when an integer value is invalid."""

    path = tmp_path / "agent-lab.toml"
    env = {}
    if source == "env":
        env["AGENT_LAB_PORT"] = "abc"
    else:
        path.write_text('port = "x"\n', encoding="utf-8")
    with pytest.raises(SettingsError, match="port"):
        load(path, env)


def test_bad_toml_names_file(tmp_path: Path) -> None:
    """Name the file when its TOML syntax is invalid."""

    path = tmp_path / "agent-lab.toml"
    path.write_text("port = [\n", encoding="utf-8")
    with pytest.raises(SettingsError, match="agent-lab.toml"):
        load(path, {})


def test_unknown_file_key_names_key(tmp_path: Path) -> None:
    """Reject a setting that the code does not use."""

    path = tmp_path / "agent-lab.toml"
    path.write_text("mystery = 1\n", encoding="utf-8")
    with pytest.raises(SettingsError, match="mystery"):
        load(path, {})


def test_settings_are_frozen() -> None:
    """Keep loaded settings from changing by accident."""

    settings = Settings()
    with pytest.raises(FrozenInstanceError):
        settings.port = 9000
