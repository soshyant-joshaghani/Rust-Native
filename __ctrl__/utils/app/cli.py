"""Scaffold new app modules."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from lib.config import ROOT

PROJECT = ROOT.parent
CTRL = "rust-native-ctrl"
KIND = "rust"

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_name(name: str) -> str:
    name = name.strip().lower().replace("-", "_")
    if not _NAME_RE.match(name):
        raise SystemExit(
            "Module name must start with a letter and contain only lowercase "
            "letters, digits, and underscores."
        )
    if name in {"sample", "base", "system", "global"}:
        raise SystemExit(f"Reserved module name: {name}")
    return name


def _write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        print(f"  skip (exists): {path.relative_to(PROJECT)}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  created: {path.relative_to(PROJECT)}")
    return True


def _title(name: str) -> str:
    return name.replace("_", " ").title()


def _backend_files(name: str) -> None:
    title = _title(name)
    base = PROJECT / "backend/src/modules/apps" / name
    _write_if_missing(base / "mod.rs", "pub mod router;\n")
    _write_if_missing(
        base / "router.rs",
        "use axum::\u007brouting::get, Json, Router\u007d;\n"
        "use serde_json::\u007bjson, Value\u007d;\n\n"
        "use crate::core::state::AppState;\n\n"
        "pub fn router() -> Router<AppState> \u007b\n"
        f'    Router::new().route("/{name}", get(root))\n'
        "}\n\n"
        "async fn root() -> Json<Value> \u007b\n"
        f'    Json(json!(\u007b "message": "{title} module" \u007d))\n'
        "}\n",
    )


def _frontend_files(name: str) -> None:
    root = PROJECT / "frontend"
    if not (root / "package.json").is_file() and (root / "web").is_dir():
        root = root / "web"
    api = root / "src/lib/modules/apps" / name / "api.ts"
    page = root / "src/routes/(dashboard)" / name / "+page.svelte"
    _write_if_missing(
        api,
        f"""export function moduleUrl(): string {{
\treturn '/api/v1/{name}';
}}
""",
    )
    title = _title(name)
    _write_if_missing(
        page,
        f"""<script lang="ts">
\timport {{ moduleUrl }} from '$lib/modules/apps/{name}/api';
</script>

<section class="rounded-xl border p-6">
\t<h2 class="text-2xl font-bold">{title}</h2>
\t<p class="mt-4 text-muted-foreground">API <code>{{moduleUrl()}}</code></p>
</section>
""",
    )


def cmd_app_create(args: argparse.Namespace) -> int:
    name = _validate_name(args.name)
    print(f"[{CTRL}] Scaffolding app module: {name}")
    _backend_files(name)
    _frontend_files(name)
    print()
    print("Next steps:")
    print(f"  1. Copy the depth of the sample module.")
    print(f"  2. Merge {name}::router::router() in backend/src/modules/apps/mod.rs.")
    print(f"  3. Run: __ctrl__\\{CTRL}.bat test backend")
    return 0


def build_app_subparser(sub: argparse._SubParsersAction) -> None:
    sp = sub.add_parser("app", help="Scaffold application modules")
    actions = sp.add_subparsers(dest="app_action", required=True)
    create_sp = actions.add_parser("create", help="Create a new app module skeleton")
    create_sp.add_argument("name", help="module name (e.g. bookmarks, orders)")
    create_sp.add_argument("--force", action="store_true", help="kept for the shared command surface")
    create_sp.set_defaults(func=cmd_app_create)
