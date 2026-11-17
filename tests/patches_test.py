"""Checks that the patch series and the patch files agree."""

import pathlib
import unittest

PATCHES = pathlib.Path(__file__).resolve().parent.parent / "patches"


def _series(directory: pathlib.Path) -> list[str]:
    """Returns the patch names a series file lists, in order."""
    lines = (directory / "series").read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line and not line.startswith("#")]


class SeriesTest(unittest.TestCase):

    def test_series_and_files_match(self) -> None:
        for directory in sorted(PATCHES.iterdir()):
            with self.subTest(project=directory.name):
                files = sorted(p.name for p in directory.glob("*.patch"))
                self.assertEqual(sorted(_series(directory)), files)

    def test_patches_are_git_mails_with_a_subject(self) -> None:
        for patch in sorted(PATCHES.glob("*/*.patch")):
            with self.subTest(patch=patch.name):
                text = patch.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("From "))
                self.assertIn("\nSubject: [PATCH] ", text)
                self.assertIn("\n---\n", text)


if __name__ == "__main__":
    unittest.main()
