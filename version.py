"""Version of the running deployment, resolved once at import.

The checkout identifies itself — branch, short commit, commit date, plus
"+dirty" for uncommitted edits:

    version-2 · b06611b · 2026-07-29

APP_VERSION in the environment (or .env) replaces the whole string — that is
the escape hatch for a deploy without git metadata, where there is nothing to
read the commit from.

Shown at the bottom of the Settings tab (GET /api/version).
"""

import os
import subprocess

from dotenv import load_dotenv

# version.py is imported before webserver.settings, so .env is not loaded yet.
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UNKNOWN_VERSION = "unknown"


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", BASE_DIR, *args],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _from_git() -> str:
    commit = _git("rev-parse", "--short", "HEAD")
    if not commit:
        return ""

    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    dirty = "+dirty" if _git("status", "--porcelain", "--untracked-files=no") else ""
    date = _git("log", "-1", "--format=%cs")

    parts = [part for part in (branch if branch != "HEAD" else "", commit + dirty, date) if part]
    return " · ".join(parts)


def _resolve() -> str:
    from_env = os.getenv("APP_VERSION", "").strip()
    if from_env:
        return from_env

    return _from_git() or UNKNOWN_VERSION


APP_VERSION = _resolve()
