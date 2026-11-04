#!/usr/bin/env python3
"""Windows Repair Toolkit: conservative diagnostics and built-in repair operations."""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

APP_NAME = "WinRepair"
USER_AGENT = "WinRepair/1.0 (+https://github.com/akc251002lko/win-repair)"
COMMAND_TIMEOUT_SECONDS = 4 * 60 * 60


class RepairError(Exception):
    """Base exception for expected application failures."""


class UnsupportedPlatformError(RepairError):
    """Raised when an operation is unavailable on this Windows version."""


class PrivilegeError(RepairError):
    """Raised when an operation requires an elevated process."""


class CommandExecutionError(RepairError):
    """Raised when a trusted Windows utility cannot be executed."""


@dataclass(frozen=True)
class SystemInfo:
    system: str
    release: str
    version: str
    machine: str
    python_version: str
    service_pack: str
    is_64bit_os: bool
    is_admin: bool


@dataclass(frozen=True)
class Task:
    task_id: str
    title: str
    description: str
    command: Tuple[str, ...]
    requires_admin: bool
    minimum_major: int = 5
    changes_system: bool = False


@dataclass
class TaskResult:
    task_id: str
    title: str
    command: List[str]
    started_at: str
    duration_seconds: float
    return_code: Optional[int]
    status: str
    output: str


def _configure_logging() -> Path:
    candidates: List[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / APP_NAME / "logs")
    candidates.append(Path(tempfile.gettempdir()) / APP_NAME / "logs")

    for directory in candidates:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            log_path = directory / "win-repair.log"
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                handlers=[
                    logging.FileHandler(str(log_path), encoding="utf-8"),
                    logging.StreamHandler(sys.stderr),
                ],
            )
            return log_path
        except OSError:
            continue

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    return Path("win-repair.log")


LOGGER = logging.getLogger(APP_NAME)


def _is_windows() -> bool:
    return os.name == "nt"


def _is_admin() -> bool:
    if not _is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _windows_major_version() -> int:
    if not _is_windows():
        raise UnsupportedPlatformError("This application only runs on Windows.")
    try:
        version = sys.getwindowsversion()
        if version.major == 6 and version.minor < 2:
            return 5
        return int(version.major)
    except (AttributeError, OSError, ValueError) as exc:
        raise UnsupportedPlatformError("Unable to identify the Windows version.") from exc


def collect_system_info() -> SystemInfo:
    release, version, _, service_pack = platform.win32_ver()
    architecture = platform.machine() or "unknown"
    return SystemInfo(
        system=platform.system(),
        release=release or "unknown",
        version=version or "unknown",
        machine=architecture,
        python_version=platform.python_version(),
        service_pack=service_pack or "none reported",
        is_64bit_os=platform.machine().endswith("64"),
        is_admin=_is_admin(),
    )


def build_task_catalog() -> Dict[str, Task]:
    tasks = {
        "system-check": Task(
            "system-check",
            "System information",
            "Collect Windows version, architecture, Python and elevation details.",
            (),
            False,
        ),
        "sfc-verify": Task(
            "sfc-verify",
            "System File Checker verification",
            "Verify protected Windows system files without attempting repairs.",
            ("sfc", "/verifyonly"),
            True,
        ),
        "sfc-repair": Task(
            "sfc-repair",
            "System File Checker repair",
            "Scan protected Windows system files and repair integrity violations where possible.",
            ("sfc", "/scannow"),
            True,
            changes_system=True,
        ),
        "dism-scan": Task(
            "dism-scan",
            "DISM component store scan",
            "Scan the Windows component store for corruption.",
            ("DISM", "/Online", "/Cleanup-Image", "/ScanHealth"),
            True,
            minimum_major=6,
        ),
        "dism-repair": Task(
            "dism-repair",
            "DISM component store repair",
            "Attempt repair of the Windows component store using Windows servicing sources.",
            ("DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"),
            True,
            minimum_major=6,
            changes_system=True,
        ),
        "chkdsk-scan": Task(
            "chkdsk-scan",
            "System volume file-system check",
            "Run CHKDSK against the Windows volume without requesting fixes or scheduling a reboot.",
            ("chkdsk", "C:"),
            True,
        ),
    }
    return tasks


def _validate_task(task: Task, info: SystemInfo) -> None:
    if not _is_windows():
        raise UnsupportedPlatformError("Repair tasks require Windows.")
    major = _windows_major_version()
    if major < task.minimum_major:
        raise UnsupportedPlatformError(
            "This operation requires a newer Windows release."
        )
    if task.requires_admin and not info.is_admin:
        raise PrivilegeError("This task requires an elevated Administrator session.")
    if task.command and shutil.which(task.command[0]) is None:
        raise CommandExecutionError("Required Windows utility was not found: " + task.command[0])


def _run_task(task: Task, execute: bool, info: SystemInfo) -> TaskResult:
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    if task.task_id == "system-check":
        output = json.dumps(asdict(info), indent=2, sort_keys=True)
        return TaskResult(task.task_id, task.title, [], started, 0.0, 0, "completed", output)

    _validate_task(task, info)
    command = list(task.command)
    if not execute:
        return TaskResult(
            task.task_id, task.title, command, started, 0.0, None,
            "planned", "Dry run only. No system changes were made.",
        )

    LOGGER.info("Starting task %s", task.task_id)
    start_time = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            shell=False,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            errors="replace",
            timeout=COMMAND_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        duration = round(time.monotonic() - start_time, 2)
        output = (completed.stdout or "").strip()
        status = "completed" if completed.returncode == 0 else "failed"
        LOGGER.info("Task %s ended with return code %s", task.task_id, completed.returncode)
        return TaskResult(
            task.task_id, task.title, command, started, duration,
            completed.returncode, status, output,
        )
    except subprocess.TimeoutExpired as exc:
        duration = round(time.monotonic() - start_time, 2)
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        return TaskResult(
            task.task_id, task.title, command, started, duration, None,
            "timed-out", str(partial) + "\nThe operation exceeded the configured timeout.",
        )
    except OSError as exc:
        raise CommandExecutionError("Unable to start " + command[0] + ": " + str(exc)) from exc


def _print_result(result: TaskResult) -> None:
    print("\n[" + result.status.upper() + "] " + result.title)
    if result.command:
        print("Command: " + subprocess.list2cmdline(result.command))
    print("Duration: " + str(result.duration_seconds) + " seconds")
    if result.output:
        print(result.output)


def _write_report(results: Sequence[TaskResult], report_path: Optional[Path]) -> Optional[Path]:
    if report_path is None:
        return None
    payload = {
        "application": APP_NAME,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "results": [asdict(result) for result in results],
    }
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        raise RepairError("Unable to write report: " + str(exc)) from exc
    return report_path


def _run_gui() -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox, scrolledtext
    except ImportError as exc:
        raise RepairError("Tkinter is unavailable in this Python installation.") from exc

    catalog = build_task_catalog()
    root = tk.Tk()
    root.title("Windows Repair Toolkit")
    root.geometry("760x620")
    root.minsize(620, 480)

    heading = tk.Label(root, text="Windows Repair Toolkit", font=("Segoe UI", 16, "bold"))
    heading.pack(anchor="w", padx=14, pady=(14, 4))
    info = collect_system_info()
    tk.Label(
        root,
        text="Windows {0} | {1} | Administrator: {2}".format(
            info.release, info.machine, "Yes" if info.is_admin else "No"
        ),
    ).pack(anchor="w", padx=14, pady=(0, 10))

    selections: Dict[str, tk.BooleanVar] = {}
    options = tk.Frame(root)
    options.pack(fill="x", padx=14)
    for task_id, task in catalog.items():
        if task_id == "system-check":
            continue
        variable = tk.BooleanVar(value=task_id in ("sfc-verify", "dism-scan", "chkdsk-scan"))
        selections[task_id] = variable
        tk.Checkbutton(
            options,
            text=task.title + (" (modifies system)" if task.changes_system else ""),
            variable=variable,
            anchor="w",
        ).pack(fill="x")

    execute_var = tk.BooleanVar(value=False)
    tk.Checkbutton(
        root,
        text="Execute selected operations (otherwise preview only)",
        variable=execute_var,
        fg="#9b2c2c",
    ).pack(anchor="w", padx=14, pady=8)

    output = scrolledtext.ScrolledText(root, wrap="word", height=18, state="disabled")
    output.pack(fill="both", expand=True, padx=14, pady=8)

    def append(text: str) -> None:
        output.configure(state="normal")
        output.insert("end", text + "\n\n")
        output.see("end")
        output.configure(state="disabled")

    def run_selected() -> None:
        execute = bool(execute_var.get())
        chosen = [catalog[key] for key, value in selections.items() if value.get()]
        if not chosen:
            messagebox.showinfo("Nothing selected", "Select at least one operation.")
            return
        if execute and not messagebox.askyesno(
            "Confirm system operations",
            "Selected Windows utilities will run. Some operations modify protected system files. Continue?",
        ):
            return
        try:
            current_info = collect_system_info()
            for task in chosen:
                result = _run_task(task, execute, current_info)
                append("[" + result.status.upper() + "] " + result.title + "\n" + result.output)
        except RepairError as exc:
            messagebox.showerror("Operation blocked", str(exc))

    tk.Button(root, text="Run selected operations", command=run_selected).pack(
        anchor="e", padx=14, pady=(0, 14)
    )
    root.mainloop()
    return 0


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Conservative Windows diagnostics and built-in repair operations."
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        choices=sorted(build_task_catalog().keys()),
        help="Operations to preview or run.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute selected Windows utilities. Without this flag, only preview.",
    )
    parser.add_argument("--report", type=Path, help="Write a JSON report to this path.")
    parser.add_argument("--gui", action="store_true", help="Launch the graphical interface.")
    parser.add_argument("--version", action="version", version="WinRepair 1.0.0")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    log_path = _configure_logging()
    LOGGER.info("Starting %s; log file: %s", APP_NAME, log_path)
    try:
        args = _parse_args(argv)
        if args.gui:
            return _run_gui()
        info = collect_system_info()
        print("Windows Repair Toolkit")
        print("OS: {0} {1} ({2})".format(info.system, info.release, info.machine))
        print("Administrator: " + ("yes" if info.is_admin else "no"))
        if not args.tasks:
            print("\nAvailable tasks:")
            for task in build_task_catalog().values():
                print("  {0:14} {1}".format(task.task_id, task.title))
            print("\nPreview: python win_repair.py --tasks sfc-verify dism-scan")
            print("Execute: python win_repair.py --tasks sfc-repair --execute")
            return 0

        results: List[TaskResult] = []
        catalog = build_task_catalog()
        for task_id in args.tasks:
            result = _run_task(catalog[task_id], bool(args.execute), info)
            results.append(result)
            _print_result(result)

        report = _write_report(results, args.report)
        if report:
            print("\nJSON report: " + str(report))
        return 1 if any(item.status in ("failed", "timed-out") for item in results) else 0
    except RepairError as exc:
        LOGGER.error("%s", exc)
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user.")
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
