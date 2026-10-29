"""rust-native-ctrl test."""

from __future__ import annotations

import argparse
import sys

from utils.dev.cli import _setup_local, _tool_argv, PROJECT

CTRL = "rust-native-ctrl"


def _run(argv_name: str, args: list[str], cwd) -> int:
    argv = _tool_argv(argv_name, *args)
    if not argv:
        return 1
    print(f"[rust-native] {' '.join(argv)}")
    import subprocess
    proc = subprocess.run(argv, cwd=cwd)
    return proc.returncode


def _run_backend() -> int:
    print("[rust-native] Backend tests (cargo test)")
    from utils.dev.cli import _rust_docker_argv, _rust_in_docker

    if _rust_in_docker():
        import subprocess

        print("[rust-native] cargo not found on PATH: running cargo test in a rust:1 container")
        return subprocess.run(_rust_docker_argv("test"), cwd=PROJECT).returncode
    return _run("cargo", ["test"], PROJECT / "backend")


def _run_frontend() -> int:
    from utils.web.store import locked_kit

    try:
        kit = locked_kit()
    except SystemExit:
        print("[rust-native] No web kit installed. Skipping frontend tests (run: rust-native-ctrl web use svelte).")
        return 0
    if kit["runtime"] != "node":
        print(f"[rust-native] {kit['label']} has no Vitest suite in this repo. Skipping frontend tests.")
        return 0
    front = PROJECT / "frontend" / "web"
    if not (front / "package.json").is_file():
        print("[rust-native] frontend/web is empty. Install it with: rust-native-ctrl web use svelte")
        return 0
    print("[rust-native] Frontend check (svelte-check)")
    return _run("npm", ["run", "check"], front)


def _run_contract(args: argparse.Namespace) -> int:
    import subprocess

    script = PROJECT / "tests" / "contract" / "contract_test.py"
    if not script.is_file():
        print(f"error: missing {script}", file=sys.stderr)
        return 1
    cmd = [sys.executable, str(script), "--base", args.base, "--local", "--jobs"]
    print("[contract] " + " ".join(cmd))
    return subprocess.run(cmd, cwd=PROJECT).returncode



def cmd_test(args: argparse.Namespace) -> int:
    if args.target == "contract":
        return _run_contract(args)
    code = _setup_local(force_install=False)
    if code != 0:
        return code
    target = args.target
    if target in ("backend", "all"):
        code = _run_backend()
        if code != 0:
            print("Backend tests failed.", file=sys.stderr)
            return code
    if target in ("frontend", "all"):
        code = _run_frontend()
        if code != 0:
            print("Frontend tests failed.", file=sys.stderr)
            return code
    if target == "all":
        print("\nAll tests passed.")
    return 0


def build_test_subparser(sub: argparse._SubParsersAction) -> None:
    sp = sub.add_parser("test", help="Run backend and frontend tests")
    sp.add_argument("target", nargs="?", default="all", choices=("all", "backend", "frontend", "contract"))
    sp.add_argument("--base", default="http://localhost:8000", help="API origin for `test contract`")
    sp.set_defaults(func=cmd_test)
