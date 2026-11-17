"""Tests the `just install <destdir>` contract that apex-image relies on."""

import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTALL = ROOT / "scripts" / "install.sh"
COMPONENTS = ROOT / "components"
FLAVORS = ROOT / "flavors"


def _component_files(parent: pathlib.Path = COMPONENTS) -> list[pathlib.Path]:
    """Returns every file under <parent>/*/usr, relative to its usr/."""
    files: list[pathlib.Path] = []
    for tree in sorted(parent.glob("*/usr")):
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

    def test_flavor_adds_its_files_to_the_base(self) -> None:
        for flavor in sorted(FLAVORS.iterdir()):
            with self.subTest(flavor=flavor.name):
                with tempfile.TemporaryDirectory() as destdir:
                    subprocess.run([INSTALL, destdir, flavor.name], check=True)
                    usr = pathlib.Path(destdir, "usr")
                    for relative in _component_files() + _component_files(
                        flavor
                    ):
                        self.assertTrue((usr / relative).is_file(), relative)

    def test_base_install_has_no_flavor_files(self) -> None:
        with tempfile.TemporaryDirectory() as destdir:
            subprocess.run([INSTALL, destdir], check=True)
            for flavor in sorted(FLAVORS.iterdir()):
                for relative in _component_files(flavor):
                    with self.subTest(path=str(relative)):
                        installed = pathlib.Path(destdir, "usr", relative)
                        self.assertFalse(installed.exists())

    def test_rejects_an_unknown_flavor(self) -> None:
        with tempfile.TemporaryDirectory() as destdir:
            result = subprocess.run(
                [INSTALL, destdir, "no-such-flavor"],
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)

    def test_requires_a_destdir(self) -> None:
        result = subprocess.run([INSTALL], capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"usage", result.stderr)


class LayoutTest(unittest.TestCase):
    """Checks the shape of components/."""

    def test_components_hold_only_usr_and_a_readme(self) -> None:
        dirs = [*COMPONENTS.iterdir(), *FLAVORS.glob("*/*")]
        for component in sorted(dirs):
            if not component.is_dir():
                continue
            with self.subTest(component=component.name):
                entries = {path.name for path in component.iterdir()}
                self.assertLessEqual(entries, {"README.md", "usr"})
                self.assertIn("README.md", entries)

    def test_no_two_components_install_the_same_path(self) -> None:
        for flavor in [None, *sorted(FLAVORS.iterdir())]:
            files = _component_files()
            if flavor is not None:
                files += _component_files(flavor)
            with self.subTest(flavor=flavor.name if flavor else "base"):
                self.assertEqual(len(files), len(set(files)))


if __name__ == "__main__":
    unittest.main()
