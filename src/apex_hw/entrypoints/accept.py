"""Runs the acceptance checks and prints one line per row.

At a terminal it guides the person at the machine through the steps that a
program cannot judge; with --no-guide, or without a terminal, those rows
need a person. A run of every row also writes a dated record, as JSON and
Markdown, to copy back into apex-hardware's docs/records/.

Exit status: 0 when every row passed or is absent, 1 when a row failed,
2 on a usage error, 3 when no row failed but some still need a person.
"""

import argparse
from collections.abc import Mapping, Sequence
import datetime
import importlib.resources
import json
import pathlib
import sys

from apex_hw.checks import acceptance
from apex_hw.checks import firmware
from apex_hw.checks import machine
from apex_hw.checks import registry
from apex_hw.kernel import record
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib
from apex_hw.platform import person as person_lib

DEFAULT_RECORD_DIR = "~/apex-acceptance"


def exit_status(results: Sequence[result.Result]) -> int:
    """Returns 1 if a row failed, 3 if one needs a person, else 0."""
    statuses = {r.status for r in results}
    if result.Status.FAIL in statuses:
        return 1
    return 3 if result.Status.NEEDS_PERSON in statuses else 0


def checker_version() -> str:
    """Returns the version that install.sh stamped, or "source tree"."""
    try:
        stamp = importlib.resources.files("apex_hw").joinpath("version.txt")
        return stamp.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "source tree"


def write_record(
    directory: pathlib.Path,
    facts: Mapping[str, str],
    records: Sequence[result.RowRecord],
) -> pathlib.Path:
    """Writes <date>-<os>-<version>.json and .md; returns the .md path.

    An existing record of the same name gets a numbered sibling instead of
    being overwritten.
    """
    directory.mkdir(parents=True, exist_ok=True)
    stem = "-".join(
        part.replace("/", "_").replace(" ", "_")
        for part in (facts["date"], facts["os_id"], facts["os_version"])
    )
    name, number = stem, 1
    while (directory / f"{name}.md").exists() or (
        directory / f"{name}.json"
    ).exists():
        number += 1
        name = f"{stem}-{number}"
    title = f"Acceptance: {facts['os']} on {facts['machine']}, {facts['date']}"
    (directory / f"{name}.json").write_text(
        record.to_json(facts, records), encoding="utf-8"
    )
    markdown = directory / f"{name}.md"
    markdown.write_text(
        record.to_markdown(title, facts, records), encoding="utf-8"
    )
    return markdown


def _parser() -> argparse.ArgumentParser:
    """Returns the command line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", nargs="*", help="rows to run (default: all)")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument(
        "--no-guide",
        action="store_true",
        help="ask nothing; rows that need a person stay unfinished",
    )
    parser.add_argument(
        "--record-dir",
        default=DEFAULT_RECORD_DIR,
        help=f"where a run of every row records it ({DEFAULT_RECORD_DIR})",
    )
    parser.add_argument(
        "--no-record", action="store_true", help="write no record"
    )
    parser.add_argument(
        "--list", action="store_true", help="list the rows and exit"
    )
    parser.add_argument(
        "--firmware-list",
        default=firmware.INSTALLED_LIST,
        help="path of firmware.txt",
    )
    return parser


def _print(results: Sequence[result.Result], as_json: bool) -> None:
    """Prints one line, or one JSON object, per row."""
    if as_json:
        rows = [
            {"row": r.row, "status": r.status.value, "value": r.value}
            for r in results
        ]
        json.dump(rows, sys.stdout, indent=2)
        print()
    else:
        for r in results:
            print(record.line(r))


def main(argv: Sequence[str] | None = None) -> int:
    """Parses arguments, runs the selected checks and reports them."""
    parser = _parser()
    args = parser.parse_args(argv)
    checks = registry.all_checks(args.firmware_list)
    if args.list:
        print("\n".join(row for row, _ in checks))
        return 0
    unknown = set(args.rows) - {row for row, _ in checks}
    if unknown:
        parser.error(f"unknown rows: {', '.join(sorted(unknown))}")
    person: person_lib.Person = person_lib.NoPerson()
    if not args.no_guide and sys.stdin.isatty():
        person = person_lib.TerminalPerson(sys.stdin, sys.stderr)
    host = host_lib.LinuxHost()
    started = datetime.datetime.now().astimezone()
    facts = {
        **machine.describe(host),
        "checker": checker_version(),
        "started": started.isoformat(timespec="seconds"),
        "date": started.date().isoformat(),
    }
    records = acceptance.run(
        [(r, c) for r, c in checks if not args.rows or r in args.rows],
        host,
        person,
    )
    _print([r.result for r in records], args.json)
    if not args.rows and not args.no_record:
        directory = pathlib.Path(args.record_dir).expanduser()
        written = write_record(directory, facts, records)
        print(f"\nRecord: {written} and its .json", file=sys.stderr)
    return exit_status([r.result for r in records])


def run() -> None:
    """Exits with main's status; the entry point of the installed program."""
    sys.exit(main())


if __name__ == "__main__":
    run()
