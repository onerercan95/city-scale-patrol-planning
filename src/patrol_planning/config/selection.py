from pathlib import Path
from typing import Optional

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_SELECTOR = PROJECT_ROOT / "configs" / "default.yaml"


def resolve_config_path(
    config_path: Optional[Path],
    selector_path: Path = DEFAULT_CONFIG_SELECTOR,
) -> Path:
    """Resolve an explicit config or the config named by the default selector."""
    if config_path is not None:
        resolved = Path(config_path)
    else:
        with selector_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        selected = payload.get("config")
        if not isinstance(selected, str) or not selected.strip():
            raise ValueError(f"{selector_path} must contain a non-empty 'config' value")
        resolved = Path(selected)
        if not resolved.is_absolute():
            resolved = selector_path.parent / resolved

    if not resolved.is_file():
        raise FileNotFoundError(f"Configuration file not found: {resolved}")
    return resolved.resolve()
