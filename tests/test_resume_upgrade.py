from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
SRC_ROOT = PROJECT_ROOT / "src"
for path in (str(SCRIPTS_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from resume_upgrade_node import _backup_set_is_complete  # noqa: E402


class ResumeBackupSetTests(unittest.TestCase):
    def test_requires_ucs_scf_archive_and_qkview(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backups_dir = Path(temp_dir)
            (backups_dir / "node.ucs").touch()
            (backups_dir / "node.tar").touch()

            self.assertFalse(_backup_set_is_complete(backups_dir))

            (backups_dir / "node.qkview").touch()

            self.assertTrue(_backup_set_is_complete(backups_dir))


if __name__ == "__main__":
    unittest.main()
