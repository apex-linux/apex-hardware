"""Tests the `just install <destdir>` contract that apex-image relies on."""

import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTALL = ROOT / "scripts" / "install.sh"
COMPONENTS = ROOT / "components"


def _component_files() -> list[pathlib.Path]:
    """Returns every file under components/*/usr, relative to its usr/."""
    files: list[pathlib.Path] = []
    for tree in sorted(COMPONENTS.glob("*/usr")):
        files.extend(
            path.relative_to(tree) for path in tree.rglob("*") if path.is_file()
        )
    return files


class InstallTest(unittest.TestCase):
    """Runs scripts/install.sh into a temporary directory."""

    def test_installs_only_under_usr(self) -> None:
        with tempfile.TemporaryDirectory() as destdir:
            subprocess.run([INSTALL, destdir], check=True)
            top = sorted(path.name for path in pathlib.Path(destdir).iterdir())
            self.assertIn(top, ([], ["usr"]))

    def test_installs_every_component_file(self) -> None:
        with tempfile.TemporaryDirectory() as destdir:
            subprocess.run([INSTALL, destdir], check=True)
            for relative in _component_files():
                with self.subTest(path=str(relative)):
                    installed = pathlib.Path(destdir, "usr", relative)
                    self.assertTrue(installed.is_file())
                    self.assertEqual(installed.stat().st_mode & 0o777, 0o644)

    def test_installs_a_runnable_acceptance_program(self) -> None:
        with tempfile.TemporaryDirectory() as destdir:
            subprocess.run([INSTALL, destdir], check=True)
            program = pathlib.Path(destdir, "usr/libexec/apex-hardware/accept")
            self.assertEqual(program.stat().st_mode & 0o777, 0o755)
            done = subprocess.run(
                [sys.executable, program, "--help"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("--json", done.stdout)

    def test_requires_a_destdir(self) -> None:
        result = subprocess.run([INSTALL], capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"usage", result.stderr)


class LayoutTest(unittest.TestCase):
    """Checks the shape of components/."""

    def test_components_hold_only_usr_and_a_readme(self) -> None:
        for component in sorted(COMPONENTS.iterdir()):
            if not component.is_dir():
                continue
            with self.subTest(component=component.name):
                entries = {path.name for path in component.iterdir()}
                self.assertLessEqual(entries, {"README.md", "usr"})
                self.assertIn("README.md", entries)

    def test_no_two_components_install_the_same_path(self) -> None:
        files = _component_files()
        self.assertEqual(len(files), len(set(files)))


if __name__ == "__main__":
    unittest.main()
