"""Small, dependency-free runtime configuration helpers.

The project deliberately avoids a dotenv dependency. Only the documented keys
below are loaded from a local environment file; arbitrary entries are ignored.
Process environment values take precedence over file values, while explicit CLI
arguments are applied later and therefore have the highest priority.
"""

from __future__ import annotations

import os
from pathlib import Path


SUPPORTED_ENV_KEYS = frozenset(
    {
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "VOICE_PPT_EDITOR_MODEL",
        "VOICE_PPT_PLANNER_MODEL",
        "VOICE_PPT_MODEL_CACHE",
        "VOICE_PPT_CODE_TIMEOUT_S",
    }
)


def read_env_file(path: str | Path) -> dict[str, str]:
    """Read supported ``KEY=value`` entries from *path*.

    Missing files are allowed because commands such as ``inspect`` and local ASR
    can run without credentials. Values may be quoted; comments and blank lines
    are ignored.
    """

    env_path = Path(path).expanduser()
    if not env_path.is_file():
        return {}

    values: dict[str, str] = {}
    with env_path.open("r", encoding="utf-8-sig") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :].lstrip()
            key, value = line.split("=", 1)
            key = key.strip().upper()
            if key not in SUPPORTED_ENV_KEYS:
                continue
            values[key] = value.strip().strip('"').strip("'")
    return values


def load_runtime_environment(path: str | Path, *, override: bool = False) -> dict[str, str]:
    """Load supported settings and return the values found in the file."""

    env_path = Path(path).expanduser()
    values = read_env_file(env_path)
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value
    os.environ["VOICE_PPT_ENV_FILE"] = str(env_path)
    return values
