"""Tests the parts of the accept program that touch no machine."""

import pathlib
import tempfile
import unittest

from apex_hw.checks import machine
from apex_hw.entrypoints import accept
from apex_hw.kernel import result

FACTS = {
    "date": "2026-11-20",
    "os_id": "apex",
    "os_version": "45",
    "os": "Apex 45",
    "machine": "ASUS M7400QC",
}
RECORDS = [
    result.RowRecord(
        result.passed("igpu", "ok"),
        (result.Evidence("automated", result.Status.PASS, "ok"),),
    )
]


class WriteRecordTest(unittest.TestCase):

    def test_names_by_date_and_system_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            where = pathlib.Path(directory, "records")
            first = accept.write_record(where, FACTS, RECORDS)
            second = accept.write_record(where, FACTS, RECORDS)
            self.assertEqual(first.name, "2026-11-20-apex-45.md")
            self.assertEqual(second.name, "2026-11-20-apex-45-2.md")
            self.assertTrue((where / "2026-11-20-apex-45-2.json").is_file())


class ExitStatusTest(unittest.TestCase):

    def test_fail_wins_over_needs_person(self) -> None:
        rows = [result.needs_person("a", ""), result.failed("b", "")]
        self.assertEqual(accept.exit_status(rows), 1)
        self.assertEqual(accept.exit_status(rows[:1]), 3)
        self.assertEqual(accept.exit_status([result.absent("c", "")]), 0)


class OsReleaseTest(unittest.TestCase):

    def test_parses_quoted_values(self) -> None:
        fields = machine.os_release(
            'NAME="Apex Linux"\nID=apex\n# note\nVERSION_ID=45\nEMPTY=\n'
        )
        self.assertEqual(fields["NAME"], "Apex Linux")
        self.assertEqual(fields["ID"], "apex")
        self.assertEqual(fields["EMPTY"], "")
        self.assertNotIn("# note", fields)


if __name__ == "__main__":
    unittest.main()
