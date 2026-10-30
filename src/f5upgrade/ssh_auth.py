from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Sequence


def run_windows_ssh_with_password(
    command: Sequence[str],
    password: str,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run a Windows OpenSSH command using a temporary SSH_ASKPASS helper."""
    if os.name != "nt" or not password:
        return subprocess.run(command, **kwargs)

    askpass_dir = Path(tempfile.mkdtemp(prefix="f5upgrade-askpass-"))
    askpass_path = askpass_dir / "askpass.cmd"
    password_b64 = base64.b64encode(password.encode("utf-8")).decode("ascii")
    try:
        askpass_path.write_text(
            "@echo off\r\n"
            "powershell -NoProfile -NonInteractive -Command "
            "\"$bytes = [Convert]::FromBase64String("
            "$env:F5UPGRADE_SSH_ASKPASS_PASSWORD); "
            "[Console]::OpenStandardOutput().Write($bytes, 0, $bytes.Length)\"\r\n",
            encoding="ascii",
        )
        env = dict(os.environ)
        env["SSH_ASKPASS"] = str(askpass_path)
        env["SSH_ASKPASS_REQUIRE"] = "force"
        env["F5UPGRADE_SSH_ASKPASS_PASSWORD"] = password_b64
        env.setdefault("DISPLAY", ":0")
        return subprocess.run(command, env=env, **kwargs)
    finally:
        askpass_path.unlink(missing_ok=True)
        askpass_dir.rmdir()
