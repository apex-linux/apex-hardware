"""Runs the acceptance checks and prints one line per row.

At a terminal it guides the person at the machine through the steps that a
program cannot judge; with --no-guide, or without a terminal, those rows
need a person.

Exit status: 0 when every row passed or is absent, 1 when a row failed,
2 on a usage error, 3 when no row failed but some still need a person.
"""

import argparse
from collections.abc import Sequence
import json
import sys

from apex_hw.checks import acceptance
from apex_hw.checks import firmware
from apex_hw.checks import registry
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib
from apex_hw.platform import person as person_lib

_LABEL = {
    result.Status.PASS: "PASS",
    result.Status.FAIL: "FAIL",
    result.Status.ABSENT: "SKIP",
    result.Status.NEEDS_PERSON: "TODO",
}


def exit_status(results: Sequence[result.Result]) -> int:
    """Returns 1 if a row failed, 3 if one needs a person, else 0."""
    statuses = {r.status for r in results}
    if result.Status.FAIL in statuses:
        return 1
    return 3 if result.Status.NEEDS_PERSON in statuses else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Parses arguments, runs the selected checks and reports them."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", nargs="*", help="rows to run (default: all)")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument(
        "--no-guide",
        action="store_true",
        help="ask nothing; rows that need a person stay unfinished",
    )
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
    selected = [(r, c) for r, c in checks if not args.rows or r in args.rows]
    person: person_lib.Person = person_lib.NoPerson()
    if not args.no_guide and sys.stdin.isatty():
        person = person_lib.TerminalPerson(sys.stdin, sys.stderr)
    records = acceptance.run(selected, host_lib.LinuxHost(), person)
    results = [record.result for record in records]
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
    return exit_status(results)


def run() -> None:
    """Exits with main's status; the entry point of the installed program."""
    sys.exit(main())


if __name__ == "__main__":
    run()
