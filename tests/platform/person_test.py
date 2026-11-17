"""Tests the terminal adapter of the Person port."""

import io
import unittest

from apex_hw.platform import person


def _person(typed: str) -> tuple[person.TerminalPerson, io.StringIO]:
    shown = io.StringIO()
    return person.TerminalPerson(io.StringIO(typed), shown), shown


class TerminalPersonTest(unittest.TestCase):

    def test_reads_yes_no_and_skip(self) -> None:
        at, _ = _person("y\nNo\ns\n")
        self.assertIs(at.ask("one?"), True)
        self.assertIs(at.ask("two?"), False)
        self.assertIsNone(at.ask("three?"))

    def test_asks_again_until_it_understands(self) -> None:
        at, shown = _person("maybe\nyes\n")
        self.assertIs(at.ask("sure?"), True)
        self.assertEqual(shown.getvalue().count("sure?"), 2)

    def test_enter_means_done_and_s_skips(self) -> None:
        at, _ = _person("\ns\n")
        self.assertTrue(at.wait("go"))
        self.assertFalse(at.wait("go"))

    def test_end_of_input_skips_everything_left(self) -> None:
        at, shown = _person("")
        self.assertIsNone(at.ask("one?"))
        self.assertFalse(at.wait("go"))
        at.tell("more")
        self.assertEqual(shown.getvalue().count("one?"), 1)
        self.assertNotIn("go", shown.getvalue())
        self.assertNotIn("more", shown.getvalue())

    def test_nobody_answers_nothing(self) -> None:
        nobody = person.NoPerson()
        self.assertFalse(nobody.wait("go"))
        self.assertIsNone(nobody.ask("one?"))


if __name__ == "__main__":
    unittest.main()
