"""
Package entry point.
Registered in pyproject.toml as:
    vidsmith = "vidsmith.main:main"

Bare ``vidsmith`` launches the interactive application. A small set of
non-interactive subcommands (``doctor``, ``--version``) are handled up front so
the tool feels like a first-class CLI without disturbing the interactive flow.
"""

from __future__ import annotations

import argparse
import sys


def _configure_windows_utf8() -> None:
    """Force UTF-8 on Windows stdio before any Rich Console is created.

    The default Windows encoding is cp1252, which cannot represent the
    box-drawing and other Unicode characters Rich uses. ``errors='replace'``
    avoids a crash if any character slips through on a legacy terminal.
    """
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(encoding="utf-8", errors="replace")


def _build_parser() -> argparse.ArgumentParser:
    from vidsmith.config import APP_NAME, APP_VERSION

    parser = argparse.ArgumentParser(
        prog="vidsmith",
        description=f"{APP_NAME} — a production-grade YouTube media downloader.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"{APP_NAME} {APP_VERSION}",
    )
    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser(
        "doctor",
        help="Inspect the environment and report missing/optional tools.",
    )
    doctor.add_argument(
        "--no-network",
        action="store_true",
        help="Skip internet / YouTube reachability checks.",
    )

    return parser


def main() -> None:
    if sys.version_info < (3, 12):
        print("VidSmith requires Python 3.12 or newer.", file=sys.stderr)
        sys.exit(1)

    _configure_windows_utf8()

    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "doctor":
        # Imported lazily so the interactive path stays fast and import-light.
        from vidsmith.cli.doctor import run_doctor

        sys.exit(run_doctor(network=not args.no_network))

    # Default: launch the interactive application. Deferred import so Console
    # objects are constructed after the UTF-8 reconfigure above.
    from vidsmith.cli.app import run
    from vidsmith.settings.store import current_settings
    from vidsmith.utils.logging import configure_logging

    configure_logging(current_settings().debug_logging)
    run()


if __name__ == "__main__":
    main()
