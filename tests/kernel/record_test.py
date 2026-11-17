"""Tests the JSON and Markdown forms of a record."""

import json
import unittest

from apex_hw.kernel import record
from apex_hw.kernel import result

Status = result.Status

RECORDS = [
    result.RowRecord(
        result.needs_person("audio", "pins ok; needs a person: speakers"),
        (
            result.Evidence("automated", Status.PASS, "pins ok"),
            result.Evidence("speakers", Status.NEEDS_PERSON, "not answered"),
        ),
    ),
    result.RowRecord(
        result.passed("igpu", "amdgpu | eDP-1"),
        (result.Evidence("automated", Status.PASS, "amdgpu | eDP-1"),),
    ),
]
FACTS = {"os": "Apex 45", "machine": "ASUS M7400QC", "checker": "abc123"}


class RecordTest(unittest.TestCase):

    def test_json_keeps_every_piece_of_evidence(self) -> None:
        data = json.loads(record.to_json(FACTS, RECORDS))
        self.assertEqual(data["schema"], record.SCHEMA)
        self.assertEqual(data["facts"]["checker"], "abc123")
        self.assertEqual(data["rows"][0]["status"], "needs_person")
        self.assertEqual(
            [e["step"] for e in data["rows"][0]["evidence"]],
            ["automated", "speakers"],
        )

    def test_markdown_summarizes_and_escapes(self) -> None:
        page = record.to_markdown("Acceptance", FACTS, RECORDS)
        self.assertIn("Result: 1 PASS, 1 TODO.", page)
        self.assertIn("| OS | Apex 45 |", page)
        self.assertIn("TODO  audio        pins ok", page)
        self.assertIn("| automated | PASS | amdgpu \\| eDP-1 |", page)
        self.assertTrue(page.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
