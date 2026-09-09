"""Minimal .env loader.

The project has no python-dotenv dependency and does not need one: hosting
platforms inject real environment variables, so this only exists to make local
development convenient. Values already present in the environment always win,
so an accidental stale .env can never override a deliberately exported variable.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

    logger.info("Loaded local environment from %s", path.name)


def set_env_value(path: Path, key: str, value: str) -> None:
    """Write a single key back to the .env file, preserving everything else.

    Used to persist the Fyers access token so a restart does not force another
    login. Rewrites in place rather than appending, so the key never duplicates.
    """
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    replaced = False

    for index, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[index] = f"{key}={value}"
            replaced = True
            break

    if not replaced:
        lines.append(f"{key}={value}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value
