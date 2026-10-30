from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
SRC_ROOT = PROJECT_ROOT / "src"
for path in (str(SCRIPTS_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from run_backup_artifacts import SSHSession  # noqa: E402


class TmosSshSessionTests(unittest.TestCase):
    def test_windows_tmos_shell_uses_util_bash_for_backup_commands(self):
        session = SSHSession("operator", "192.0.2.10", password="password")

        with (
            patch("run_backup_artifacts.os.name", "nt"),
            patch(
                "run_backup_artifacts.run_windows_ssh_with_password",
                side_effect=[
                    SimpleNamespace(returncode=1),
                    SimpleNamespace(returncode=0),
                    SimpleNamespace(returncode=0, stdout="", stderr=""),
                ],
            ) as ssh_run,
        ):
            session.open()
            session.run("tmsh save sys ucs backup", timeout_sec=30)

        self.assertEqual("tmsh show sys version", ssh_run.call_args_list[0].args[0][-1])
        self.assertEqual("show sys version", ssh_run.call_args_list[1].args[0][-1])
        self.assertEqual(
            "run util bash -c 'tmsh save sys ucs backup'",
            ssh_run.call_args_list[2].args[0][-1],
        )


if __name__ == "__main__":
    unittest.main()
