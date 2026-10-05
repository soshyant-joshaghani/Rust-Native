"""Kit catalog and frontend/kit.lock.json."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lib.config import ROOT

PROJECT = ROOT.parent
KITS_FILE = ROOT / "kits.json"
LOCK_FILE = PROJECT / "frontend" / "kit.lock.json"
WEB_DIR = PROJECT / "frontend" / "web"

_SKIP_DIRS = {
    "node_modules",
    ".svelte-kit",
    "build",
    ".next",
    ".nuxt",
    ".output",
    "__pycache__",
    ".git",
}

USE_HINT = "web use {svelte|next|nuxt|rio}"


def load_catalog() -> list[dict]:
    data = json.loads(KITS_FILE.read_text(encoding="utf-8"))
    return data["kits"]


def get_kit(kit_id: str) -> dict:
    for kit in load_catalog():
        if kit["id"] == kit_id:
            return kit
    known = ", ".join(item["id"] for item in load_catalog())
    raise SystemExit(f"Unknown kit {kit_id!r}. Known: {known}")


def read_lock() -> dict | None:
    if not LOCK_FILE.is_file():
        return None
    return json.loads(LOCK_FILE.read_text(encoding="utf-8"))


def write_lock(payload: dict) -> None:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def require_lock() -> dict:
    lock = read_lock()
    if lock is None:
        raise SystemExit(
            "No web kit installed.\n"
            f"  rust-native-ctrl.bat {USE_HINT}\n"
            "  rust-native-ctrl.bat web list"
        )
    return lock


def locked_kit() -> dict:
    lock = require_lock()
    return get_kit(lock["kit"])


def dev_spec(python: Path) -> tuple[list[str], Path, str]:
    """Return (argv, cwd, runtime) for the installed web kit."""
    kit = locked_kit()
    argv = [str(python) if part == "{python}" else part for part in kit["dev"]]
    cwd_rel = kit.get("cwd") or "."
    cwd = PROJECT if cwd_rel == "." else (PROJECT / cwd_rel)
    return argv, cwd, kit["runtime"]


def slot_is_placeholder(web: Path = WEB_DIR) -> bool:
    if not web.exists():
        return True
    files = [path for path in web.rglob("*") if path.is_file()]
    if not files:
        return True
    return all(path.name in ("README.md", ".gitkeep") and path.parent == web for path in files)


def tree_sha256(web: Path = WEB_DIR) -> str:
    digest = hashlib.sha256()
    if not web.is_dir():
        return digest.hexdigest()
    paths = []
    for path in web.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(web).parts):
            continue
        paths.append(path)
    for path in sorted(paths, key=lambda item: item.relative_to(web).as_posix()):
        rel = path.relative_to(web).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def tree_is_dirty(lock: dict | None = None) -> bool:
    lock = read_lock() if lock is None else lock
    if lock is None:
        return False
    recorded = lock.get("content_sha256")
    if not recorded:
        return False
    return tree_sha256() != recorded
