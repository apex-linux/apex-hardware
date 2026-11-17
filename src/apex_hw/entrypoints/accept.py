"""Runs the acceptance checks and prints one line per row.

Exit status: 0 when no row fails, 1 when a row fails, 2 on a usage error.
"""

import argparse
from collections.abc import Sequence
import json
import sys

from apex_hw.checks import firmware
from apex_hw.checks import registry
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

_LABEL = {
    result.Status.PASS: "PASS",
    result.Status.FAIL: "FAIL",
    result.Status.ABSENT: "SKIP",
}


def _run(check: registry.Check, row: str, host: host_lib.Host) -> result.Result:
    """Runs one check; a crash fails its row instead of the whole run."""
    try:
        return check(host)
    except Exception as error:  # pylint: disable=broad-exception-caught
        return result.failed(row, f"check crashed: {error!r}")


def main(argv: Sequence[str] | None = None) -> int:
    """Parses arguments, runs the selected checks and reports them."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", nargs="*", help="rows to run (default: all)")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument(
        "--firmware-list",
        default=firmware.INSTALLED_LIST,
        help="path of firmware.txt",
    )
    args = parser.parse_args(argv)
    checks = registry.all_checks(args.firmware_list)
    unknown = set(args.rows) - {row for row, _ in checks}
    if unknown:
        parser.error(f"unknown rows: {', '.join(sorted(unknown))}")
    host = host_lib.LinuxHost()
    results = [
        _run(check, row, host)
        for row, check in checks
        if not args.rows or row in args.rows
    ]
    if args.json:
        rows = [
            {"row": r.row, "status": r.status.value, "value": r.value}
            for r in results
        ]
        json.dump(rows, sys.stdout, indent=2)
        print()
    else:
        for r in results:
            print(f"{_LABEL[r.status]}  {r.row:<12} {r.value}")
    return 1 if any(r.status is result.Status.FAIL for r in results) else 0


def run() -> None:
    """Exits with main's status; the entry point of the installed program."""
    sys.exit(main())


if __name__ == "__main__":
    run()
