"""rust-native-ctrl prod — local compose.yml helpers."""

from __future__ import annotations

import argparse

from utils.logs.cli import attach_prod_logs_subparser
from utils.remote_run import run_remote_script

BRAND = "rust-native"
CTRL = "rust-native-ctrl"

ACTIONS: dict[str, str] = {
    "start": "start-prod",
    "stop": "stop-prod",
    "reset": "reset-prod",
    "backup-acme": "backup-acme",
    "restore-acme": "restore-acme",
    "prune-build": "prune-docker-build",
    "migrate-acme": "migrate-letsencrypt-from-volume",
    "setup-ubuntu": "setup-ubuntu",
}


def cmd_prod(args: argparse.Namespace) -> int:
    action = args.prod_action
    stem = ACTIONS.get(action)
    if not stem:
        print(f"error: unknown prod action {action!r}")
        return 1
    extra: list[str] = []
    if action == "migrate-acme" and getattr(args, "volume", None):
        extra.append(args.volume)
    return run_remote_script(stem, brand=BRAND, extra=extra)


def _prod_help(_: argparse.Namespace) -> int:
    print(
        f"usage: {CTRL}.bat prod {{start,stop,reset,backup-acme,restore-acme,"
        "prune-build,migrate-acme,setup-ubuntu,logs}\n"
        "\n"
        f"examples:\n"
        f"  {CTRL}.bat prod start\n"
        f"  {CTRL}.bat prod stop\n"
    )
    return 0


def build_prod_subparser(sub: argparse._SubParsersAction) -> None:
    sp = sub.add_parser(
        "prod",
        help="Local production compose helpers (see also SSH start/stop)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"examples:\n"
            f"  {CTRL}.bat prod start\n"
            f"  {CTRL}.bat prod stop\n"
            f"  {CTRL}.bat prod reset\n"
            f"\n"
            "SSH: start | stop | update | backup-acme"
        ),
    )
    sp.set_defaults(func=_prod_help)
    actions = sp.add_subparsers(dest="prod_action", required=False)

    for name, help_ in [
        ("start", "compose up -d --build (local)"),
        ("stop", "compose down - keep volumes + SSL"),
        ("reset", "Wipe DB/Redis volumes + app images; keep SSL"),
        ("backup-acme", "Copy acme.json to parent .foxg-ssl-backups"),
        ("restore-acme", "Restore acme.json from parent backup"),
        ("prune-build", "Backup SSL then docker builder prune -af"),
        ("migrate-acme", "Copy acme.json from legacy Docker volume"),
        ("setup-ubuntu", "One-time Ubuntu VM bootstrap (Linux only)"),
    ]:
        action_sp = actions.add_parser(name, help=help_)
        if name == "migrate-acme":
            action_sp.add_argument(
                "volume",
                nargs="?",
                default=None,
                help="legacy volume name (optional)",
            )
        action_sp.set_defaults(func=cmd_prod, prod_action=name)

    attach_prod_logs_subparser(actions)
