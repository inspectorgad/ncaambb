"""Loads config/sources.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from . import CONFIG_DIR


def load_sources_config(path: Path | None = None) -> dict[str, Any]:
    path = path or CONFIG_DIR / "sources.yaml"
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)
