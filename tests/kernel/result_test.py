"""Tests how a row's evidence becomes its verdict."""

import unittest

from apex_hw.kernel import result

Evidence = result.Evidence
Status = result.Status


class CombineTest(unittest.TestCase):

    def test_automated_alone_passes(self) -> None:
        found = result.combine(
            "igpu", [Evidence("automated", Status.PASS, "a")]
        )
        self.assertEqual(found, result.passed("igpu", "a"))

    def test_absent_ignores_the_rest(self) -> None:
        found = result.combine(
            "audio",
            [
                Evidence("automated", Status.ABSENT, "no codec"),
                Evidence("speakers", Status.FAIL, "no"),
            ],
        )
        self.assertIs(found.status, Status.ABSENT)

    def test_unanswered_step_needs_a_person(self) -> None:
        found = result.combine(
            "audio",
            [
                Evidence("automated", Status.PASS, "pins ok"),
                Evidence("speakers", Status.NEEDS_PERSON, "not answered"),
                Evidence("mic", Status.PASS, "yes"),
            ],
        )
        self.assertEqual(
            found,
            result.needs_person("audio", "pins ok; needs a person: speakers"),
        )

    def test_a_failed_step_fails_the_row_first(self) -> None:
        found = result.combine(
            "audio",
            [
                Evidence("automated", Status.PASS, "pins ok"),
                Evidence("speakers", Status.NEEDS_PERSON, "not answered"),
                Evidence("mic", Status.FAIL, "no: level?"),
            ],
        )
        self.assertEqual(
            found, result.failed("audio", "mic: no: level?; pins ok")
        )

    def test_failed_automated_leads(self) -> None:
        found = result.combine(
            "wifi",
            [
                Evidence("automated", Status.FAIL, "down"),
                Evidence("after resume", Status.FAIL, "still down"),
            ],
        )
        self.assertEqual(
            found, result.failed("wifi", "down; after resume: still down")
        )

    def test_every_step_passed(self) -> None:
        found = result.combine(
            "display",
            [
                Evidence("automated", Status.PASS, "90 Hz"),
                Evidence("brightness", Status.PASS, "yes"),
            ],
        )
        self.assertEqual(
            found, result.passed("display", "90 Hz; confirmed: brightness")
        )


if __name__ == "__main__":
    unittest.main()
