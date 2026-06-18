from pathlib import Path

import pytest

from patrol_planning.config.selection import resolve_config_path


def test_resolve_explicit_config(tmp_path: Path) -> None:
    config = tmp_path / "scenario.yaml"
    config.write_text("run_name: test\n", encoding="utf-8")

    assert resolve_config_path(config) == config.resolve()


def test_resolve_relative_config_from_selector(tmp_path: Path) -> None:
    config = tmp_path / "scenario.yaml"
    selector = tmp_path / "default.yaml"
    config.write_text("run_name: test\n", encoding="utf-8")
    selector.write_text('config: "scenario.yaml"\n', encoding="utf-8")

    assert resolve_config_path(None, selector) == config.resolve()


def test_selector_requires_config_value(tmp_path: Path) -> None:
    selector = tmp_path / "default.yaml"
    selector.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="non-empty 'config'"):
        resolve_config_path(None, selector)
