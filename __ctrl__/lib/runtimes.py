"""Ensure system Node.js / npm is available for local frontend tooling."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _refresh_path_windows() -> None:
    """Reload Machine+User PATH into this process (winget does not update it)."""
    try:
        import winreg
    except ImportError:
        return

    parts: list[str] = []
    for hive, subkey in (
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
        (winreg.HKEY_CURRENT_USER, r"Environment"),
    ):
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
                if value:
                    parts.append(str(value))
        except OSError:
            continue

    extras: list[str] = []
    local = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    for candidate in (
        Path(program_files) / "nodejs",
        Path(local) / "Programs" / "nodejs",
        Path(local) / "Microsoft" / "WinGet" / "Links",
    ):
        if candidate.is_dir():
            extras.append(str(candidate))

    merged = os.pathsep.join([*extras, *parts])
    if merged:
        os.environ["PATH"] = merged


def _refresh_path_unix() -> None:
    home = Path.home()
    extras: list[str] = []
    for brew in (Path("/opt/homebrew/bin"), Path("/usr/local/bin")):
        if brew.is_dir():
            extras.append(str(brew))
    local_bin = home / ".local" / "bin"
    if local_bin.is_dir():
        extras.append(str(local_bin))
    if extras:
        os.environ["PATH"] = os.pathsep.join([*extras, os.environ.get("PATH", "")])


def refresh_path() -> None:
    if sys.platform == "win32":
        _refresh_path_windows()
    else:
        _refresh_path_unix()


def _run(cmd: list[str]) -> int:
    print(f"[runtimes] {' '.join(cmd)}")
    proc = subprocess.run(cmd, check=False)
    return proc.returncode


def _install_nodejs() -> int:
    """Install Node.js LTS (+ npm) via the OS package manager."""
    print("[runtimes] npm not found. Installing Node.js LTS...")
    if sys.platform == "win32":
        if not shutil.which("winget"):
            print(
                "error: winget not found. Install Node.js from https://nodejs.org/",
                file=sys.stderr,
            )
            return 1
        return _run(
            [
                "winget",
                "install",
                "-e",
                "--id",
                "OpenJS.NodeJS.LTS",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
        )

    uname = os.uname().sysname if hasattr(os, "uname") else ""
    if uname == "Darwin" or sys.platform == "darwin":
        if not shutil.which("brew"):
            print(
                "error: Homebrew not found. Install from https://brew.sh/ then retry.",
                file=sys.stderr,
            )
            return 1
        return _run(["brew", "install", "node"])

    if shutil.which("apt-get"):
        code = _run(["sudo", "apt-get", "update", "-y"])
        if code != 0:
            return code
        return _run(
            [
                "sudo",
                "env",
                "DEBIAN_FRONTEND=noninteractive",
                "apt-get",
                "install",
                "-y",
                "nodejs",
                "npm",
            ]
        )

    print(
        "error: no supported package manager to install Node.js. "
        "Install from https://nodejs.org/",
        file=sys.stderr,
    )
    return 1


def ensure_nodejs() -> int:
    """Return 0 if npm is on PATH (installing if needed), else 1."""
    if shutil.which("npm"):
        return 0
    code = _install_nodejs()
    if code != 0:
        return code
    refresh_path()
    if shutil.which("npm"):
        return 0
    print(
        "error: npm still not found after Node install. "
        "Open a new terminal or reboot, then retry.",
        file=sys.stderr,
    )
    return 1
