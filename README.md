# WinRepair — Windows Repair Toolkit

[![CI](https://github.com/akc251002lko/win-repair/actions/workflows/ci.yml/badge.svg)](https://github.com/akc251002lko/win-repair/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-blue.svg)](https://www.microsoft.com/windows)

A conservative Windows diagnostics and repair utility with a command-line interface and a lightweight Tkinter desktop interface. WinRepair orchestrates trusted Windows servicing tools; it does not replace Windows recovery media, vendor diagnostics, or a qualified technician.

## What This Repository Is For

WinRepair provides a single, auditable entry point for selected built-in Windows maintenance operations:

- Collect OS, architecture, Python and elevation information.
- Verify protected system files with System File Checker.
- Run SFC repair when explicitly requested.
- Scan or repair the Windows component store with DISM on supported Windows releases.
- Perform a non-repair CHKDSK inspection of the Windows volume.
- Export operation results to JSON for support and troubleshooting.

The application is deliberately conservative: operations are preview-only unless `--execute` is supplied. Repair operations require an elevated Administrator session.

## Features

- Python standard library only; no pip dependencies.
- CLI and optional Tkinter GUI.
- Explicit task selection and dry-run default.
- Administrator and platform checks.
- Bounded subprocess execution with timeouts and captured output.
- Structured JSON reports and local log files.
- Automated unit tests and GitHub Actions CI.

## Compatibility

| Target | Notes |
|---|---|
| Windows 7 SP1 | Core Python 3.8-compatible application and SFC/CHKDSK task paths; Python 3.8 is end-of-life. |
| Windows 8 / 8.1 | Core operations; DISM component-store tasks are available where the installed servicing stack supports them. |
| Windows 10 | Supported target; use a currently maintained Python release where available. |
| Windows 11 | Supported target; Windows 11 is 64-bit only. |

Architecture support depends on the installed Python interpreter and Windows edition. Windows 11 does not have an x86 edition. Compatibility claims require validation on actual target devices; CI on a modern Windows runner does not certify legacy Windows releases.

Python 3.8.10 is the final Python 3.8 release with official Windows 7 support, but Python 3.8 is end-of-life and no longer receives security fixes. Use a maintained Python version on supported modern Windows systems.

## Requirements

- Windows 7 SP1 or later for Windows operations.
- Python 3.8 or later; Tkinter is needed only for the GUI.
- Administrator privileges for SFC, DISM and CHKDSK tasks.
- Built-in Windows utilities available on the target installation.

## How To Use

Open Command Prompt or PowerShell in the repository directory.

Show available operations:

```powershell
python src\win_repair.py
```

Collect system information:

```powershell
python src\win_repair.py --tasks system-check --report reports\system.json
```

Preview diagnostic operations without executing them:

```powershell
python src\win_repair.py --tasks sfc-verify chkdsk-scan
```

Execute SFC verification (run the terminal as Administrator):

```powershell
python src\win_repair.py --tasks sfc-verify --execute
```

Run a repair only after reviewing the implications:

```powershell
python src\win_repair.py --tasks sfc-repair --execute --report reports\sfc.json
```

Launch the graphical interface:

```powershell
python src\win_repair.py --gui
```

## Safety Model

- No operation executes unless `--execute` is provided (GUI has a separate unchecked-by-default execution option).
- SFC repair and DISM restore operations modify Windows servicing state.
- Create a current backup and ensure reliable power before repairs.
- DISM may require Windows Update or a valid repair source.
- CHKDSK is invoked without repair flags; it does not schedule an offline repair.
- The tool does not delete user files, modify the registry, disable services, or change startup entries.
- Review command output and JSON reports. A successful process exit does not guarantee every underlying Windows issue is resolved.

## Development and Tests

Run the unit tests with:

```powershell
python -m unittest discover -s tests -v
```

CI runs the unit test suite on Windows with multiple Python versions. Legacy OS support must be verified separately on real Windows 7 SP1 and Windows 8/8.1 devices.

## Project Structure

```text
src/
  win_repair.py
tests/
  test_win_repair.py
.github/
  workflows/
    ci.yml
SECURITY.md
README.md
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and pull request guidance.

## Security

Please do not publish logs or JSON reports containing private system information. See [SECURITY.md](SECURITY.md) for responsible vulnerability reporting.

## Community

Questions, feedback and project updates: [Join the Telegram community](https://t.me/githubakc251002lko).

## License

MIT License. See [LICENSE](LICENSE).
