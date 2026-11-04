# Contributing

Thank you for helping improve WinRepair.

## Before submitting changes

1. Open an issue describing the bug or proposed improvement.
2. Keep the application and tests standard-library-only.
3. Preserve preview-first behavior. Any system-changing operation must require explicit execution consent and appropriate privilege checks.
4. Never add automatic reboot behavior or silently broaden the set of system commands.
5. Add unit tests for command construction, platform guards, privilege checks, timeout handling, and report generation.
6. Run the complete test suite on Windows:

   `python -m unittest discover -s tests -v`

## Pull requests

Explain the user impact, affected Windows/Python versions, tests performed, and any known servicing limitations. Real Windows repair operations should be validated only in disposable virtual machines with snapshots.

## Security issues

Do not disclose exploitable vulnerabilities in public issues. Follow the reporting guidance in [SECURITY.md](SECURITY.md).
