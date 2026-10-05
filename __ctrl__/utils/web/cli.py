"""rust-native-ctrl web — download a kit frontend into frontend/web."""

from __future__ import annotations

import argparse
import io
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

from utils.web.dockerfiles import rewrite_dockerfiles
from utils.web.store import (
    PROJECT,
    LOCK_FILE,
    WEB_DIR,
    get_kit,
    load_catalog,
    read_lock,
    slot_is_placeholder,
    tree_is_dirty,
    tree_sha256,
    write_lock,
)

_USER_AGENT = "rust-native-ctrl"


def _request(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def _commit_sha(kit: dict) -> str:
    url = f"https://api.github.com/repos/{kit['github']}/commits/{kit['branch']}"
    try:
        payload = json.loads(_request(url).decode("utf-8"))
    except Exception as exc:
        print(f"warning: could not read commit SHA ({exc})")
        return "unknown"
    sha = payload.get("sha")
    if not isinstance(sha, str) or not sha:
        print("warning: GitHub commit response had no sha")
        return "unknown"
    return sha


def _archive_prefix(kit: dict) -> str:
    return f"{kit['archive_root']}-{kit['branch']}/frontend/"


def _extract_frontend(blob: bytes, kit: dict, dest: Path) -> None:
    prefix = _archive_prefix(kit)
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
        for member in archive.getmembers():
            name = member.name.replace("\\", "/")
            if not name.startswith(prefix) or name == prefix.rstrip("/"):
                continue
            rel = name[len(prefix) :]
            if not rel or rel.endswith("/"):
                continue
            rel_path = Path(rel)
            if rel_path.is_absolute() or ".." in rel_path.parts:
                raise SystemExit(f"Refusing to extract outside frontend/web: {rel}")
            target = dest / rel_path
            if member.issym() or member.islnk():
                continue
            if not member.isfile():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                continue
            target.write_bytes(source.read())
            copied += 1
    if copied == 0:
        raise SystemExit(f"Archive had no files under {prefix}")
    print(f"  extracted {copied} files into frontend/web")


def _clear_web() -> None:
    if WEB_DIR.exists():
        shutil.rmtree(WEB_DIR)
    WEB_DIR.mkdir(parents=True, exist_ok=True)


def _install_local(kit: dict) -> int:
    """Copy a sibling template frontend when kits.json sets source."""
    source = (PROJECT / kit["source"]).resolve()
    if not source.is_dir():
        raise SystemExit(f"Missing frontend at {source}")
    print(f"[rust-native] Copying {kit['label']} from {source}")
    _clear_web()
    shutil.copytree(
        source,
        WEB_DIR,
        ignore=shutil.ignore_patterns("node_modules", ".svelte-kit", "build", ".git"),
        dirs_exist_ok=True,
    )
    _rewrite_copied_web(WEB_DIR)
    rewrite_dockerfiles(WEB_DIR, kit["id"])
    payload = {
        "kit": kit["id"],
        "source": kit["source"],
        "repo": kit.get("repo", ""),
        "content_sha256": tree_sha256(),
    }
    write_lock(payload)
    print(f"Installed {kit['label']} into frontend/web")
    return 0


def _rewrite_copied_web(dest: Path) -> None:
    api = dest / "src" / "lib" / "modules" / "base" / "api.ts"
    if api.is_file() and "backend/src/app/app" in api.read_text(encoding="utf-8"):
        text = api.read_text(encoding="utf-8").replace(
            "from '../../../../../backend/src/app/app'",
            "from '../../../../../../backend/src/app/app'",
        )
        api.write_text(text, encoding="utf-8")
    pkg_path = dest / "package.json"
    if not pkg_path.is_file():
        return
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    deps = pkg.setdefault("dependencies", {})
    if "@hono-svelte/backend" in deps or "@hono-svelte/contracts" in deps:
        deps["@hono-svelte/backend"] = "file:../../../backend"
        deps["@hono-svelte/contracts"] = "file:../../../backend/contracts"
        pkg_path.write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")


def install_kit(kit_id: str, *, replace: bool, force: bool) -> int:
    kit = get_kit(kit_id)
    lock = read_lock()
    if lock is not None and not replace:
        current = lock.get("kit")
        if current == kit_id:
            raise SystemExit(
                f"{kit['label']} is already installed.\n"
                "  rust-native-ctrl.bat web update\n"
                "  rust-native-ctrl.bat web use "
                f"{kit_id} --replace"
            )
        raise SystemExit(
            f"frontend/web is {current}. Switching to {kit_id} needs --replace.\n"
            f"  rust-native-ctrl.bat web use {kit_id} --replace"
        )
    if lock is None and not slot_is_placeholder() and not replace:
        raise SystemExit(
            "frontend/web already has files and no kit lock.\n"
            f"  rust-native-ctrl.bat web use {kit_id} --replace"
        )
    if lock is not None and tree_is_dirty(lock) and not force and replace:
        raise SystemExit(
            "frontend/web has local edits. Re-run with --force to replace them."
        )

    if kit.get("source"):
        return _install_local(kit)


    archive_url = (
        f"https://github.com/{kit['github']}/archive/refs/heads/{kit['branch']}.tar.gz"
    )
    print(f"[rust-native] Downloading {kit['label']} ({kit['branch']})")
    print(f"  {archive_url}")
    sha = _commit_sha(kit)
    blob = _request(archive_url)
    _clear_web()
    _extract_frontend(blob, kit, WEB_DIR)
    rewrite_dockerfiles(WEB_DIR, kit_id)
    payload = {
        "kit": kit_id,
        "repo": kit["repo"],
        "branch": kit["branch"],
        "commit": sha,
        "content_sha256": tree_sha256(),
    }
    write_lock(payload)
    print(f"Installed {kit['label']} @ {sha}")
    print(f"Lock: {LOCK_FILE.relative_to(WEB_DIR.parent.parent)}")
    print("Commit frontend/web and frontend/kit.lock.json if this product should ship that UI.")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    lock = read_lock()
    current = lock.get("kit") if lock else None
    print(f"{'ID':<8} {'LABEL':<14} {'BRANCH':<8} REPO")
    print("-" * 72)
    for kit in load_catalog():
        mark = "*" if kit["id"] == current else " "
        print(
            f"{mark}{kit['id']:<7} {kit['label']:<14} {kit['branch']:<8} {kit['repo']}"
        )
    if current:
        print(f"\ninstalled: {current} ({lock.get('commit')})")
    else:
        print("\ninstalled: (none) - rust-native-ctrl.bat web use <kit>")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    lock = read_lock()
    if lock is None:
        print("No web kit installed.")
        print("  rust-native-ctrl.bat web use {svelte|next|nuxt|rio}")
        return 1
    dirty = "yes" if tree_is_dirty(lock) else "no"
    print(f"kit:     {lock.get('kit')}")
    print(f"repo:    {lock.get('repo')}")
    print(f"branch:  {lock.get('branch')}")
    print(f"commit:  {lock.get('commit')}")
    print(f"dirty:   {dirty}")
    print(f"path:    {WEB_DIR}")
    return 0


def cmd_use(args: argparse.Namespace) -> int:
    return install_kit(args.kit, replace=args.replace, force=args.force)


def cmd_update(args: argparse.Namespace) -> int:
    lock = read_lock()
    if lock is None:
        raise SystemExit(
            "No web kit installed.\n  rust-native-ctrl.bat web use {svelte|next|nuxt|rio}"
        )
    if tree_is_dirty(lock) and not args.force:
        raise SystemExit(
            "frontend/web has local edits. Re-run with --force to replace them.\n"
            "  rust-native-ctrl.bat web update --force"
        )
    return install_kit(lock["kit"], replace=True, force=True)


def build_web_subparser(sub: argparse._SubParsersAction) -> None:
    web = sub.add_parser("web", help="Download a web kit into frontend/web")
    nested = web.add_subparsers(dest="web_command")

    list_parser = nested.add_parser("list", help="List web kits")
    list_parser.set_defaults(func=cmd_list)

    use = nested.add_parser("use", help="Install a kit frontend from GitHub")
    use.add_argument("kit", choices=[item["id"] for item in load_catalog()])
    use.add_argument("--replace", action="store_true", help="Replace an existing frontend/web")
    use.add_argument("--force", action="store_true", help="Replace even if frontend/web has local edits")
    use.set_defaults(func=cmd_use)

    status = nested.add_parser("status", help="Show the installed kit")
    status.set_defaults(func=cmd_status)

    update = nested.add_parser("update", help="Re-fetch the locked kit branch")
    update.add_argument("--force", action="store_true", help="Replace local edits in frontend/web")
    update.set_defaults(func=cmd_update)

    web.set_defaults(func=lambda _: web.print_help() or 0)
