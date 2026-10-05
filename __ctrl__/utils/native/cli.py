"""Native client builds. Android uses Gradle. Windows uses dotnet (WinUI 3)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

CTRL = Path(__file__).resolve().parents[2]
PLATFORMS_FILE = CTRL / "platforms.json"


def echo(message: str) -> None:
    print(message, flush=True)


def run(cmd: list[str], *, cwd: Path) -> int:
    quoted = " ".join(f'"{part}"' if " " in part else part for part in cmd)
    echo(f"$ {quoted}")
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return 0


def load_platforms() -> list[dict]:
    data = json.loads(PLATFORMS_FILE.read_text(encoding="utf-8"))
    return data["platforms"]


def get_platform(platform_id: str) -> dict:
    for platform in load_platforms():
        if platform["id"] == platform_id:
            return platform
    known = ", ".join(item["id"] for item in load_platforms())
    raise SystemExit(f"Unknown platform {platform_id!r}. Known: {known}")


def platform_dir(platform: dict) -> Path:
    return (CTRL / platform["path"]).resolve()


def require_ready(platform: dict) -> None:
    if platform.get("status") != "ready":
        raise SystemExit(f"{platform['id']} is {platform.get('status', 'planned')}, not ready to build")


def resolve_targets(raw: str) -> list[dict]:
    if raw == "all":
        return [item for item in load_platforms() if item.get("status") == "ready"]
    return [get_platform(raw)]


def variant_spec(platform: dict, name: str) -> dict:
    variants = platform.get("variants") or {}
    if name not in variants:
        known = ", ".join(sorted(variants)) or "(none)"
        raise SystemExit(f"Unknown variant {name!r}. Known: {known}")
    return variants[name]


def gradle_wrapper(android_dir: Path) -> Path:
    name = "gradlew.bat" if sys.platform == "win32" else "gradlew"
    path = android_dir / name
    if not path.is_file():
        raise SystemExit(f"Gradle wrapper not found: {path}")
    return path


def android_sdk(android_dir: Path) -> Path | None:
    props = android_dir / "local.properties"
    if props.is_file():
        for line in props.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("sdk.dir="):
                raw = line.split("=", 1)[1].strip().replace("\\\\", "\\")
                path = Path(raw)
                if path.is_dir():
                    return path
    env = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if env and Path(env).is_dir():
        return Path(env)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidate = Path(local) / "Android" / "Sdk"
        if candidate.is_dir():
            return candidate
    return None


def adb_path(android_dir: Path) -> Path | None:
    sdk = android_sdk(android_dir)
    if sdk is None:
        return None
    name = "adb.exe" if sys.platform == "win32" else "adb"
    path = sdk / "platform-tools" / name
    return path if path.is_file() else None


def cmd_list(_: argparse.Namespace) -> int:
    print(f"{'ID':<10} {'LABEL':<12} {'STATUS':<10} PATH")
    print("-" * 72)
    for platform in load_platforms():
        print(
            f"{platform['id']:<10} {platform.get('label', ''):<12} "
            f"{platform.get('status', ''):<10} {platform_dir(platform)}"
        )
    return 0


def build_android(platform: dict, variant: str) -> Path:
    require_ready(platform)
    root = platform_dir(platform)
    sdk = android_sdk(root)
    props = root / "local.properties"
    if sdk is not None and not props.is_file():
        posix = str(sdk).replace("\\", "/")
        escaped = posix.replace(":", "\\:").replace("/", "\\\\")
        props.write_text(f"sdk.dir={escaped}\n", encoding="utf-8")
    spec = variant_spec(platform, variant)
    run([str(gradle_wrapper(root)), spec["gradle_task"], "--no-daemon"], cwd=root)
    out = root / spec["artifact"]
    if not out.is_file():
        raise SystemExit(f"Build finished but artifact missing: {out}")
    echo(f"artifact: {out}")
    return out


def build_win(platform: dict, variant: str) -> Path:
    require_ready(platform)
    root = platform_dir(platform)
    spec = variant_spec(platform, variant)
    project = root / platform["project"]
    cmd = [
        "dotnet",
        "build",
        str(project),
        "-c",
        spec["configuration"],
        "-p:GenerateAppxPackageOnBuild=false",
        "-p:EnableMsixTooling=false",
        "-p:WindowsPackageType=None",
        "-p:AppxGeneratePriEnabled=false",
    ]
    run(cmd, cwd=root)
    out = root / spec["artifact"]
    if not out.is_file():
        raise SystemExit(f"Build finished but artifact missing: {out}")
    echo(f"artifact: {out}")
    return out


def _launch_android(root: Path, platform: dict, apk: Path) -> None:
    adb = adb_path(root)
    if adb is None:
        echo("Android SDK or adb not found. Built the APK and skipped install.")
        return
    devices = subprocess.run([str(adb), "devices"], capture_output=True, text=True, check=False)
    lines = [line for line in (devices.stdout or "").splitlines()[1:] if line.strip().endswith("device")]
    if not lines:
        echo(f"No Android device attached. APK is at {apk}")
        return
    run([str(adb), "install", "-r", str(apk)], cwd=root)
    run(
        [
            str(adb),
            "shell",
            "am",
            "start",
            "-n",
            f"{platform['package']}/{platform['activity']}",
        ],
        cwd=root,
    )


def cmd_build(args: argparse.Namespace) -> int:
    for platform in resolve_targets(args.platform):
        if platform["id"] == "android":
            build_android(platform, args.variant)
        elif platform["id"] == "win":
            build_win(platform, args.variant)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    platform = get_platform(args.platform)
    require_ready(platform)
    if platform["id"] == "android":
        apk = build_android(platform, args.variant)
        _launch_android(platform_dir(platform), platform, apk)
        return 0
    if platform["id"] == "win":
        exe = build_win(platform, args.variant)
        echo(f"launch: {exe}")
        subprocess.Popen([str(exe)], cwd=str(exe.parent))
        return 0
    raise SystemExit(f"Cannot run {platform['id']}")


def cmd_clean(args: argparse.Namespace) -> int:
    for platform in resolve_targets(args.platform):
        root = platform_dir(platform)
        if platform["id"] == "android":
            wrapper = gradle_wrapper(root)
            if wrapper.is_file():
                run([str(wrapper), "clean", "--no-daemon"], cwd=root)
        elif platform["id"] == "win":
            project = root / platform["project"]
            run(["dotnet", "clean", str(project)], cwd=root)
    return 0


def build_native_subparser(sub: argparse._SubParsersAction) -> None:
    native = sub.add_parser("native", help="Build Android and Windows client apps")
    nested = native.add_subparsers(dest="native_command")
    ids = [item["id"] for item in load_platforms()] + ["all"]

    list_parser = nested.add_parser("list", help="List native client platforms")
    list_parser.set_defaults(func=cmd_list)

    build = nested.add_parser("build", help="Build a native client")
    build.add_argument("platform", choices=ids)
    build.add_argument("--variant", default="debug", choices=["debug", "release"])
    build.set_defaults(func=cmd_build)

    run_parser = nested.add_parser("run", help="Build and launch a native client")
    run_parser.add_argument("platform", choices=[item["id"] for item in load_platforms()])
    run_parser.add_argument("--variant", default="debug", choices=["debug", "release"])
    run_parser.set_defaults(func=cmd_run)

    clean = nested.add_parser("clean", help="Clean a native build")
    clean.add_argument("platform", choices=ids)
    clean.set_defaults(func=cmd_clean)

    native.set_defaults(func=lambda _: native.print_help() or 0)
