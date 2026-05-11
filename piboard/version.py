"""Runtime version helpers for release and Pi acceptance checks."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent
BUILD_INFO_FILE = APP_ROOT / "BUILD_INFO"
VERSION_FILE = REPO_ROOT / "VERSION"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _read_build_info(path: Path = BUILD_INFO_FILE) -> Dict[str, str]:
    info: Dict[str, str] = {}
    text = _read_text(path)
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            info[key.strip()] = value.strip()
    return info


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short=12", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def runtime_version() -> Dict[str, str]:
    """Return a small, JSON-safe version marker for local and Pi runtimes."""
    build = _read_build_info()
    version = (
        os.environ.get("PIBOARD_VERSION", "").strip()
        or build.get("version", "")
        or _read_text(VERSION_FILE)
        or "unknown"
    )
    commit = (
        os.environ.get("PIBOARD_COMMIT", "").strip()
        or build.get("commit", "")
        or _git_commit()
        or "unknown"
    )
    return {
        "version": version,
        "commit": commit,
        "tag": os.environ.get("PIBOARD_TAG", "").strip() or build.get("tag", ""),
        "deployed_at_utc": build.get("deployed_at_utc", ""),
        "source": build.get("source", "git" if commit != "unknown" else ""),
    }
