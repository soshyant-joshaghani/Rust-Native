"""rust-native-ctrl dev — run/stop local Docker Desktop / host app stacks."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from lib.config import ROOT
from lib.runtimes import ensure_nodejs
from utils.web.store import dev_spec, locked_kit, require_lock

# __ctrl__ lives under rust-native/; the compose + apps root is the parent.
PROJECT = ROOT.parent

RUN_ORDER = ("infra", "apps")
STOP_ORDER = ("apps", "infra")
TARGETS = ("infra", "apps", "all")

COMPOSE_PROJECT_NAME = "rust-native-dev"
COMPOSE_FILE = "compose.dev.yml"
APP_STARTUP_TIMEOUT_S = 180.0
FULL_INFRA_SERVICES = ("db", "redis", "proxy", "adminer")
SLIM_INFRA_SERVICES = ("db", "proxy", "adminer")

FRONTEND_DEV_PORT = 5000

# (window_title, port) — host processes; port None = no listener (e.g. background worker)
APP_PORTS = (
    ("rust-native-backend", 8000),
    ("rust-native-worker", None),
    ("rust-native-frontend", FRONTEND_DEV_PORT),
)

STACK_OPEN_URLS: dict[str, tuple[str, ...]] = {
    "infra": (
        "http://adminer.localhost/",
        "http://localhost:8080/",
    ),
    "apps": (
        "http://dashboard.localhost/",
        "http://api.localhost/docs",
        "http://api.localhost/sdoc",
    ),
}


def _require_cmd(name: str) -> str | None:
    path = shutil.which(name)
    if not path:
        print(f"error: '{name}' not found on PATH", file=sys.stderr)
        return None
    return path


def _npm_argv(*args: str) -> list[str] | None:
    """Build argv that can launch npm.cmd on Windows (CreateProcess can't)."""
    npm = _require_cmd("npm")
    if not npm:
        return None
    if sys.platform == "win32":
        return ["cmd", "/c", npm, *args]
    return [npm, *args]


def _tool_argv(name: str, *args: str) -> list[str] | None:
    """Launch cargo/dotnet/npm, including Windows *.cmd shims."""
    exe = _require_cmd(name)
    if not exe:
        return None
    if sys.platform == "win32":
        return ["cmd", "/c", exe, *args]
    return [exe, *args]


def _rust_in_docker() -> bool:
    """No host Rust toolchain: run cargo inside the official rust image instead."""
    return shutil.which("cargo") is None and shutil.which("docker") is not None


def _rust_docker_argv(*cargo_args: str, name: str | None = None, publish: str | None = None) -> list[str]:
    argv = ["docker", "run", "--rm"]
    if name:
        argv += ["--name", name]
    if publish:
        argv += ["-p", publish]
    argv += [
        "--add-host", "host.docker.internal:host-gateway",
        "-e", "APP_HOST=0.0.0.0",
        "-e", "POSTGRES_SERVER=host.docker.internal",
        "-e", "REDIS_HOST=host.docker.internal",
        "-v", f"{PROJECT}:/work",
        "-v", "rust-native-cargo:/usr/local/cargo/registry",
        "-v", "rust-native-target:/work/backend/target",
        "-w", "/work/backend",
        "rust:1",
        "cargo", *cargo_args,
    ]
    return argv


def _run_npm(*args: str, **kwargs) -> subprocess.CompletedProcess | None:
    argv = _npm_argv(*args)
    if not argv:
        return None
    return subprocess.run(argv, **kwargs)


def _resolve_targets(target: str, *, order: tuple[str, ...]) -> tuple[str, ...]:
    if target == "all":
        return order
    return (target,)


def _ensure_env() -> None:
    env = PROJECT / ".env"
    example = PROJECT / ".env.example"
    if env.is_file():
        return
    if example.is_file():
        shutil.copy(example, env)
        print(f"created {env} from .env.example")
    else:
        print(f"warn: no .env or .env.example in {PROJECT}", file=sys.stderr)


def _open_stack_urls(targets: tuple[str, ...]) -> None:
    urls: list[str] = []
    for t in targets:
        for url in STACK_OPEN_URLS.get(t, ()):
            if url not in urls:
                urls.append(url)
    for url in urls:
        print(f"opening {url}")
        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"warn: could not open {url}: {exc}", file=sys.stderr)


def _compose(*args: str, check: bool = True) -> int:
    if not _require_cmd("docker"):
        return 1
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, *args]
    print(f"[rust-native] {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=PROJECT)
    if check and proc.returncode != 0:
        return proc.returncode
    return proc.returncode


def _wait_postgres(service: str, *, timeout_s: float = 120.0) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        proc = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                COMPOSE_FILE,
                "exec",
                "-T",
                service,
                "pg_isready",
                "-U",
                "postgres",
            ],
            cwd=PROJECT,
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0:
            return 0
        time.sleep(2)
    print(f"error: {service} not ready within {timeout_s:.0f}s", file=sys.stderr)
    return 1


def _wait_redis(*, timeout_s: float = 60.0) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        proc = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                COMPOSE_FILE,
                "exec",
                "-T",
                "redis",
                "redis-cli",
                "ping",
            ],
            cwd=PROJECT,
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0 and b"PONG" in (proc.stdout or b""):
            return 0
        time.sleep(2)
    print(f"error: redis not ready within {timeout_s:.0f}s", file=sys.stderr)
    return 1


def _venv_python() -> Path | None:
    if sys.platform == "win32":
        py = PROJECT / ".venv" / "Scripts" / "python.exe"
    else:
        py = PROJECT / ".venv" / "bin" / "python"
    return py if py.is_file() else None


def _setup_local(*, force_install: bool = False) -> int:
    """Fetch Rust crates and install the Svelte frontend."""
    _ensure_env()
    if ensure_nodejs() != 0:
        return 1
    if _rust_in_docker():
        print("[rust-native] cargo not found on PATH: the backend runs in a rust:1 container (no hot reload)")
        print("[rust-native] cargo build --bins (once, so the API and the worker do not race on the crate cache)")
        proc = subprocess.run(_rust_docker_argv("build", "--bins"), cwd=PROJECT)
        if proc.returncode != 0:
            return proc.returncode
    else:
        if _tool_argv("cargo", "--version") is None:
            return 1
        print("[rust-native] cargo fetch")
        proc = subprocess.run(_tool_argv("cargo", "fetch"), cwd=PROJECT / "backend")
        if proc.returncode != 0:
            return proc.returncode
    front = PROJECT / "frontend" / "web"
    if (front / "package.json").is_file():
        print("[rust-native] npm install in " + str(front.relative_to(PROJECT)))
        proc = _run_npm("install", cwd=front)
        if proc is None or proc.returncode != 0:
            return 1 if proc is None else proc.returncode
    else:
        print("[rust-native] frontend/web is empty. Install it with: rust-native-ctrl web use svelte")
    print("Local environment ready.")
    return 0



def _rio_importable(py: Path) -> bool:
    proc = subprocess.run(
        [str(py), "-c", "import rio"],
        cwd=PROJECT,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def _run_migrations() -> int:
    print("[rust-native] SQL migrations run when the API process starts.")
    return 0



def _port_listening(port: int) -> bool:
    if sys.platform == "win32":
        return bool(_pids_on_port_windows(port))
    return bool(_pids_on_port_unix(port))


def _wait_ports(ports: tuple[int, ...], *, timeout_s: float = APP_STARTUP_TIMEOUT_S) -> list[int]:
    deadline = time.time() + timeout_s
    pending = set(ports)
    last_log = time.time()
    while pending and time.time() < deadline:
        ready = {p for p in pending if _port_listening(p)}
        pending -= ready
        if pending:
            now = time.time()
            if now - last_log >= 15.0:
                print(f"  still waiting for port(s) {sorted(pending)}...")
                last_log = now
            time.sleep(0.5)
    return sorted(pending)


def _pids_on_port_windows(port: int) -> set[int]:
    proc = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: set[int] = set()
    for line in (proc.stdout or "").splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        if parts[3].upper() != "LISTENING":
            continue
        local = parts[1]
        if not (local.endswith(f":{port}") or local.endswith(f"]:{port}")):
            continue
        try:
            pid = int(parts[4])
        except ValueError:
            continue
        if pid > 0:
            pids.add(pid)
    return pids


def _pids_on_port_unix(port: int) -> set[int]:
    pids: set[int] = set()
    if shutil.which("lsof"):
        proc = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if line.isdigit():
                pids.add(int(line))
        return pids
    if shutil.which("fuser"):
        proc = subprocess.run(
            ["fuser", f"{port}/tcp"],
            capture_output=True,
            text=True,
            check=False,
        )
        for token in (proc.stdout or "").replace("\n", " ").split():
            digits = "".join(c for c in token if c.isdigit())
            if digits:
                pids.add(int(digits))
    return pids


def _kill_pid(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            return
        except PermissionError:
            subprocess.run(["kill", "-9", str(pid)], check=False)


def _start_infra(*, slim: bool = False) -> int:
    services = SLIM_INFRA_SERVICES if slim else FULL_INFRA_SERVICES

    code = _setup_local()
    if code != 0:
        return code

    code = _compose("up", "-d", *services)
    if code != 0:
        return code
    code = _compose("up", "-d", "--force-recreate", "--no-deps", "proxy")
    if code != 0:
        return code

    print("[rust-native] Waiting for Postgres...")
    if _wait_postgres("db") != 0:
        return 1

    if not slim:
        print("[rust-native] Waiting for Redis...")
        if _wait_redis() != 0:
            return 1

    code = _run_migrations()
    if code != 0:
        return code

    if slim:
        print("Infra ready (slim): DB + Adminer + Traefik — no Redis.")
    else:
        print("Infra ready (full): DB + Redis + Adminer + Traefik.")
    return 0


def _backend_env() -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(PROJECT / "backend"),
    }


def _quote_cmd_arg(arg: str) -> str:
    """Quote a token for cmd.exe if it contains whitespace/special chars."""
    if not arg or any(c in arg for c in ' \t"&|<>()^%'):
        return '"' + arg.replace('"', '""') + '"'
    return arg


def _start_named_console(
    title: str,
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> None:
    """Open a titled console like start-rust-native-dev.bat (`start "title" cmd /k …`).

    Uses shell=True so cmd.exe parses the line; argv is joined with cmd-safe quoting
    (avoids Python list2cmdline turning quotes into \\\").
    """
    inner = " ".join(_quote_cmd_arg(a) for a in args)
    cmdline = f'start "{title}" /D {_quote_cmd_arg(str(cwd))} cmd /k {inner}'
    subprocess.Popen(cmdline, shell=True, env=env)


def _app_specs(*, slim: bool) -> list[tuple[str, list[str], Path, dict[str, str], int | None]]:
    env = dict(os.environ)
    if _rust_in_docker():
        api = _rust_docker_argv("run", "--bin", "api", name="rust-native-backend", publish="8000:8000")
    else:
        api = _tool_argv(*["cargo", "run", "--bin", "api"])
    if not api:
        return []
    specs: list[tuple[str, list[str], Path, dict[str, str], int | None]] = [
        ("rust-native-backend", api, PROJECT / "backend", env, 8000),
    ]
    if not slim:
        if _rust_in_docker():
            worker = _rust_docker_argv("run", "--bin", "worker", name="rust-native-worker")
        else:
            worker = _tool_argv(*["cargo", "run", "--bin", "worker"])
        if not worker:
            return []
        specs.append(("rust-native-worker", worker, PROJECT / "backend", env, None))
    front = _tool_argv(*["npm", "run", "dev"])
    if not front:
        return []
    specs.append(("rust-native-frontend", front, PROJECT / "frontend", env, FRONTEND_DEV_PORT))
    return specs



def _spawn_apps_windows(*, slim: bool = False) -> int:
    specs = _app_specs(slim=slim)
    if not specs:
        print("error: could not build app commands. Run setup-local.", file=sys.stderr)
        return 1

    wait_ports: list[int] = []
    for title, args, cwd, env, port in specs:
        if port is not None and _port_listening(port):
            print(f"  {title}: already listening on :{port}")
            continue
        print(f"  {title}: starting (new console)...")
        _start_named_console(title, args, cwd=cwd, env=env)
        if port is not None:
            wait_ports.append(port)

    if wait_ports:
        print(f"  waiting for app ports :8000, :{FRONTEND_DEV_PORT}...")
        missing = _wait_ports(tuple(wait_ports))
        if missing:
            print(
                f"error: apps did not listen on port(s) {missing} within {int(APP_STARTUP_TIMEOUT_S)}s. "
                "Check the new console windows for errors.",
                file=sys.stderr,
            )
            return 1
    return 0


def _spawn_apps_unix(*, slim: bool = False) -> int:
    specs = _app_specs(slim=slim)
    if not specs:
        print("error: could not build app commands. Run setup-local.", file=sys.stderr)
        return 1

    wait_ports: list[int] = []
    for title, cmd, cwd, env, port in specs:
        if port is not None and _port_listening(port):
            print(f"  {title}: already listening on :{port}")
            continue
        from utils.logs.cli import open_host_log
        try:
            log_fh, log_path = open_host_log(title)
        except KeyError:
            log_fh, log_path = None, None
        if log_path is not None:
            print(f"  {title}: starting (log: __ctrl__/logs/{log_path.name})")
        else:
            print(f"  {title}: starting...")
        env = {**env, "PYTHONUNBUFFERED": "1"}
        subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=log_fh if log_fh is not None else subprocess.DEVNULL,
            stderr=subprocess.STDOUT if log_fh is not None else subprocess.DEVNULL,
            start_new_session=True,
        )
        if log_fh is not None:
            log_fh.close()
        if port is not None:
            wait_ports.append(port)

    if wait_ports:
        print(f"  waiting for app ports :8000, :{FRONTEND_DEV_PORT}...")
        missing = _wait_ports(tuple(wait_ports))
        if missing:
            print(
                f"error: apps did not listen on port(s) {missing} within {int(APP_STARTUP_TIMEOUT_S)}s.",
                file=sys.stderr,
            )
            return 1
    return 0


def _start_apps(*, slim: bool = False) -> int:
    code = _setup_local()
    if code != 0:
        return code

    _stop_apps()

    profile = "slim" if slim else "full"
    print(f"[rust-native] Starting apps ({profile}): backend + frontend" + ("" if slim else " + worker"))
    if sys.platform == "win32":
        code = _spawn_apps_windows(slim=slim)
    else:
        code = _spawn_apps_unix(slim=slim)
    if code != 0:
        return code

    print()
    print("Dev stack ready (hot reload on save):")
    print("  Dashboard:   http://dashboard.localhost")
    print("  Sample Notes http://dashboard.localhost/sample/notes")
    print("  API docs:    http://api.localhost/docs")
    print("  Scalar:      http://api.localhost/sdoc")
    print("  Adminer:     http://adminer.localhost")
    print("  Traefik:     http://localhost:8080")
    print()
    print(f"Direct: http://localhost:{FRONTEND_DEV_PORT}  http://localhost:8000/docs  http://localhost:8000/sdoc")
    if not slim:
        print("Worker: rust-native-worker (Redis queue)")
    print("Stop with: rust-native-ctrl.bat dev stop all")
    return 0


def _stop_apps() -> int:
    print("[rust-native] Stopping host apps (backend / frontend)...")
    killed: set[int] = set()
    in_docker = _rust_in_docker()
    if shutil.which("docker"):
        subprocess.run(
            ["docker", "rm", "-f", "rust-native-backend", "rust-native-worker"],
            capture_output=True,
            check=False,
        )
    for _title, port in APP_PORTS:
        if port is None:
            continue
        if in_docker and port == 8000:
            continue  # published by Docker: never kill the Docker proxy process
        if sys.platform == "win32":
            pids = _pids_on_port_windows(port)
        else:
            pids = _pids_on_port_unix(port)
        for pid in pids:
            if pid in killed:
                continue
            print(f"  kill pid {pid} (port {port})")
            _kill_pid(pid)
            killed.add(pid)

    if sys.platform == "win32":
        for title, _port in APP_PORTS:
            subprocess.run(
                ["taskkill", "/F", "/FI", f"WINDOWTITLE eq {title}*"],
                capture_output=True,
                check=False,
            )

    if not killed:
        print("  (no listeners found on app ports; closed matching consoles if any)")
    else:
        print("Host apps stopped.")
    return 0


def _compose_stop() -> int:
    code = _compose("stop")
    if code != 0:
        return code
    print("Infra stopped (containers kept).")
    return 0


def _compose_down(*, volumes: bool = False) -> int:
    cmd = ["down", "--remove-orphans"]
    if volumes:
        cmd.append("-v")
        print("[rust-native] compose down -v  (WIPES VOLUMES)")
    code = _compose(*cmd)
    if code != 0:
        return code
    if volumes:
        _cleanup_leftover_volumes()
        print("Infra removed; named volumes wiped.")
    else:
        print("Infra removed (volumes kept).")
    return 0


def _list_volume_names() -> list[str]:
    proc = subprocess.run(
        ["docker", "volume", "ls", "-q"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def _cleanup_leftover_volumes() -> None:
    prefix_us = f"{COMPOSE_PROJECT_NAME}_"
    for name in _list_volume_names():
        if name.startswith(prefix_us):
            print(f"  removing leftover volume {name}")
            subprocess.run(
                ["docker", "volume", "rm", "-f", name],
                capture_output=True,
                check=False,
            )
    print("  pruning dangling anonymous volumes...")
    proc = subprocess.run(
        ["docker", "volume", "prune", "-f"],
        capture_output=True,
        text=True,
        check=False,
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if out:
        for line in out.splitlines():
            print(f"  {line}")


def _run_one(target: str, *, slim: bool = False) -> int:
    if target == "infra":
        return _start_infra(slim=slim)
    if target == "apps":
        return _start_apps(slim=slim)
    print(f"error: unknown target {target!r}", file=sys.stderr)
    return 1


def _stop_one(target: str) -> int:
    if target == "infra":
        return _compose_stop()
    if target == "apps":
        return _stop_apps()
    print(f"error: unknown target {target!r}", file=sys.stderr)
    return 1


def _down_one(target: str) -> int:
    if target == "infra":
        return _compose_down(volumes=False)
    if target == "apps":
        return _stop_apps()
    print(f"error: unknown target {target!r}", file=sys.stderr)
    return 1


def _wipe_one(target: str) -> int:
    if target == "infra":
        return _compose_down(volumes=True)
    if target == "apps":
        return _stop_apps()
    print(f"error: unknown target {target!r}", file=sys.stderr)
    return 1


def cmd_dev_run(args: argparse.Namespace) -> int:
    slim = bool(getattr(args, "slim", False))
    targets = _resolve_targets(args.target, order=RUN_ORDER)
    for t in targets:
        code = _run_one(t, slim=slim)
        if code != 0:
            return code
    _open_stack_urls(targets)
    return 0


def cmd_dev_stop(args: argparse.Namespace) -> int:
    for t in _resolve_targets(args.target, order=STOP_ORDER):
        code = _stop_one(t)
        if code != 0:
            return code
    return 0


def cmd_dev_down(args: argparse.Namespace) -> int:
    for t in _resolve_targets(args.target, order=STOP_ORDER):
        code = _down_one(t)
        if code != 0:
            return code
    return 0


def cmd_dev_reset(args: argparse.Namespace) -> int:
    slim = bool(getattr(args, "slim", False))
    target = args.target
    print(
        f"WARNING: dev reset {target} removes compose named volumes "
        "(Postgres data for infra)."
    )
    for t in _resolve_targets(target, order=STOP_ORDER):
        code = _wipe_one(t)
        if code != 0:
            return code
    run_targets = _resolve_targets(target, order=RUN_ORDER)
    for t in run_targets:
        code = _run_one(t, slim=slim)
        if code != 0:
            return code
    _open_stack_urls(run_targets)
    return 0


def cmd_dev_purge(args: argparse.Namespace) -> int:
    target = args.target
    print(
        f"WARNING: dev purge {target} removes compose named volumes "
        "(Postgres data for infra). Stack will stay down."
    )
    for t in _resolve_targets(target, order=STOP_ORDER):
        code = _wipe_one(t)
        if code != 0:
            return code
    return 0


def _dev_help(args: argparse.Namespace) -> int:
    _ = args
    print(
        "usage: rust-native-ctrl.bat dev {run|start,stop,down,purge,reset} {infra,apps,all}\n"
        "\n"
        "examples:\n"
        "  rust-native-ctrl.bat dev run all\n"
        "  rust-native-ctrl.bat dev run all --slim\n"
        "  rust-native-ctrl.bat dev start all\n"
        "  rust-native-ctrl.bat dev stop apps\n"
        "  rust-native-ctrl.bat dev down all\n"
        "  rust-native-ctrl.bat dev purge infra\n"
        "  rust-native-ctrl.bat dev reset all\n"
        "\n"
        "run/start: compose up + host api, frontend, and worker (full)\n"
        "  --slim:         DB + apps only (no Redis / no worker)\n"
        "stop:   compose stop / kill host apps (containers kept)\n"
        "down:   compose down / kill host apps (volumes kept)\n"
        "purge:  compose down -v (wipe volumes, do not start)\n"
        "reset:  compose down -v then run (wipe volumes)\n"
        "order:  run infra->apps; stop/down/purge/reset: apps->infra\n"
        "Local only - not SSH / production VMs."
    )
    return 0


def build_dev_subparser(sub: argparse._SubParsersAction) -> None:
    sp = sub.add_parser(
        "dev",
        help="Run/stop/down/purge/reset local Docker Desktop / host app stacks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  rust-native-ctrl.bat dev run all\n"
            "  rust-native-ctrl.bat dev run all --slim\n"
            "  rust-native-ctrl.bat dev start all\n"
            "  rust-native-ctrl.bat dev stop apps\n"
            "  rust-native-ctrl.bat dev down all\n"
            "  rust-native-ctrl.bat dev purge infra\n"
            "  rust-native-ctrl.bat dev reset all\n"
            "\n"
            "run/start: compose up + host api, frontend, and worker (full)\n"
            "  --slim:         DB + apps only (no Redis / no worker)\n"
            "stop:   compose stop / kill host apps (containers kept)\n"
            "down:   compose down / kill host apps (volumes kept)\n"
            "purge:  compose down -v (wipe volumes, do not start)\n"
            "reset:  compose down -v then run (wipe volumes)\n"
            "order:  run infra->apps; stop/down/purge/reset: apps->infra\n"
            "Local only - not SSH / production VMs."
        ),
    )
    sp.set_defaults(func=_dev_help)

    actions = sp.add_subparsers(dest="dev_action", required=False)

    for name, help_, fn in [
        ("run", "Start local stack(s)", cmd_dev_run),
        ("start", "Alias for run", cmd_dev_run),
        ("stop", "Stop services (compose stop — keep containers)", cmd_dev_stop),
        ("down", "Remove containers/networks (compose down — keep volumes)", cmd_dev_down),
        ("purge", "Wipe Docker volumes and leave stack down", cmd_dev_purge),
        ("reset", "Wipe Docker volumes then start again", cmd_dev_reset),
    ]:
        action_sp = actions.add_parser(name, help=help_)
        action_sp.add_argument(
            "target",
            choices=list(TARGETS),
            help="which local stack to act on",
        )
        if name in ("run", "start", "reset"):
            action_sp.add_argument(
                "--slim",
                action="store_true",
                help="slim runtime: skip Redis and background worker (official lightweight mode)",
            )
        action_sp.set_defaults(func=fn)



    from utils.logs.cli import attach_dev_logs_subparser

    attach_dev_logs_subparser(actions)


def cmd_setup_local(args: argparse.Namespace) -> int:
    """Top-level: create/refresh project .venv + npm deps."""
    if getattr(args, "force", False):
        venv = PROJECT / ".venv"
        if venv.is_dir():
            print("[rust-native] Removing existing .venv (--force)...")
            shutil.rmtree(venv)
        nm = PROJECT / "node_modules"
        if nm.is_dir():
            print("[rust-native] Removing node_modules (--force)...")
            shutil.rmtree(nm)
    return _setup_local(force_install=True)
