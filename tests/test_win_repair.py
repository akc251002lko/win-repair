"""Unit tests for WinRepair's safe planning and reporting behavior."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import win_repair


class WinRepairTests(unittest.TestCase):
    def setUp(self):
        self.info = win_repair.SystemInfo(
            system="Windows", release="10", version="10.0",
            machine="AMD64", python_version="3.12.0",
            service_pack="none reported", is_64bit_os=True, is_admin=True,
        )

    def test_catalog_contains_safe_and_repair_operations(self):
        catalog = win_repair.build_task_catalog()
        self.assertIn("sfc-verify", catalog)
        self.assertIn("sfc-repair", catalog)
        self.assertIn("dism-scan", catalog)
        self.assertTrue(catalog["sfc-repair"].changes_system)
        self.assertFalse(catalog["sfc-verify"].changes_system)

    def test_system_check_returns_json_without_running_command(self):
        result = win_repair._run_task(
            win_repair.build_task_catalog()["system-check"], False, self.info
        )
        self.assertEqual(result.status, "completed")
        self.assertEqual(json.loads(result.output)["system"], "Windows")

    @mock.patch("src.win_repair._is_windows", return_value=True)
    @mock.patch("src.win_repair.sys.getwindowsversion")
    @mock.patch("src.win_repair.shutil.which", return_value="C:\\Windows\\System32\\sfc.exe")
    def test_sfc_dry_run_does_not_execute(self, _which, get_version, _windows):
        get_version.return_value = mock.Mock(major=10, minor=0)
        task = win_repair.build_task_catalog()["sfc-verify"]
        with mock.patch("src.win_repair.subprocess.run") as run:
            result = win_repair._run_task(task, False, self.info)
        run.assert_not_called()
        self.assertEqual(result.status, "planned")
        self.assertEqual(result.command, ["sfc", "/verifyonly"])

    @mock.patch("src.win_repair._is_windows", return_value=True)
    @mock.patch("src.win_repair.sys.getwindowsversion")
    def test_dism_is_rejected_on_windows_7(self, get_version, _windows):
        get_version.return_value = mock.Mock(major=6, minor=1, service_pack="Service Pack 1", service_pack_major=1)
        task = win_repair.build_task_catalog()["dism-scan"]
        with mock.patch("src.win_repair.shutil.which", return_value="DISM.exe"):
            with self.assertRaises(win_repair.UnsupportedPlatformError):
                win_repair._validate_task(task, self.info)

    @mock.patch("src.win_repair._is_windows", return_value=True)
    @mock.patch("src.win_repair.sys.getwindowsversion")
    def test_task_minimum_windows_version_is_enforced(self, get_version, _windows):
        get_version.return_value = mock.Mock(major=6, minor=1)
        task = win_repair.Task(
            "future-task", "Future task", "Requires Windows 8 or later.",
            (), False, minimum_major=6,
        )
        with self.assertRaises(win_repair.UnsupportedPlatformError):
            win_repair._validate_task(task, self.info)


    @mock.patch("src.win_repair._is_windows", return_value=True)
    @mock.patch("src.win_repair.sys.getwindowsversion")
    def test_windows_vista_is_rejected(self, get_version, _windows):
        get_version.return_value = mock.Mock(major=6, minor=0)
        with self.assertRaises(win_repair.UnsupportedPlatformError):
            win_repair._windows_major_version()

    @mock.patch("src.win_repair._is_windows", return_value=True)
    @mock.patch("src.win_repair.sys.getwindowsversion")
    def test_windows_7_requires_service_pack_one(self, get_version, _windows):
        get_version.return_value = mock.Mock(major=6, minor=1, service_pack="", service_pack_major=0)
        with self.assertRaises(win_repair.UnsupportedPlatformError):
            win_repair._windows_major_version()

    def test_admin_required_for_repair_tasks(self):
        task = win_repair.build_task_catalog()["sfc-repair"]
        unprivileged = win_repair.SystemInfo(
            system="Windows", release="10", version="10",
            machine="AMD64", python_version="3.12",
            service_pack="", is_64bit_os=True, is_admin=False,
        )
        with mock.patch("src.win_repair._is_windows", return_value=True):
            with mock.patch("src.win_repair.sys.getwindowsversion", return_value=mock.Mock(major=10, minor=0)):
                with self.assertRaises(win_repair.PrivilegeError):
                    win_repair._validate_task(task, unprivileged)

    def test_json_report_is_written(self):
        result = win_repair.TaskResult(
            "system-check", "System information", [], "2026-01-01T00:00:00+00:00",
            0.0, 0, "completed", "{}",
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "report.json"
            returned = win_repair._write_report([result], target)
            self.assertEqual(returned, target)
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["results"][0]["task_id"], "system-check")


if __name__ == "__main__":
    unittest.main()
