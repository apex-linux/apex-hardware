"""Checks that requires.txt names what the rules and checks use."""

import ast
import pathlib
import re
import unittest

from apex_hw.kernel import firmware

ROOT = pathlib.Path(__file__).resolve().parent.parent
REQUIRES = ROOT / "requires.txt"
CHECKS = ROOT / "src" / "apex_hw" / "checks"
FIRMWARE_LIST = (
    ROOT / "components/firmware/usr/share/apex-hardware/firmware.txt"
)
# Commands that only exist on other distributions, as fallbacks.
_NOT_ON_FEDORA = {"dpkg-query"}


def _entries() -> list[tuple[str, str]]:
    """Returns (rpm, path) pairs."""
    pairs = []
    for line in REQUIRES.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            rpm, path = line.split()
            pairs.append((rpm, path))
    return pairs


def _commands() -> set[str]:
    """Returns the programs the checks run: the first item of argv lists."""
    found = set()
    for path in CHECKS.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "run"):
                continue
            argv = node.args[0]
            if isinstance(argv, ast.List) and argv.elts:
                first = argv.elts[0]
                if isinstance(first, ast.Constant):
                    found.add(str(first.value))
    # Lists built ahead of the call.
    text = "\n".join(p.read_text(encoding="utf-8") for p in CHECKS.glob("*.py"))
    found |= set(re.findall(r'^\s+\["([a-z][a-z0-9-]*)",', text, re.MULTILINE))
    found |= set(re.findall(r'^\w+_COMMAND = \[\n\s+"([^"]+)"', text, re.M))
    return found


class RequiresTest(unittest.TestCase):

    def test_lines_are_rpm_and_absolute_path(self) -> None:
        for line in REQUIRES.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            with self.subTest(line=line):
                self.assertRegex(line, r"^[A-Za-z0-9][\w.+-]* /\S+$")

    def test_every_command_the_checks_run_is_required(self) -> None:
        paths = {path for _, path in _entries()}
        commands = _commands() - _NOT_ON_FEDORA
        self.assertIn("pw-dump", commands)
        for command in sorted(commands):
            with self.subTest(command=command):
                self.assertIn(f"/usr/bin/{command}", paths)

    def test_every_firmware_glob_is_required(self) -> None:
        paths = {path for _, path in _entries()}
        entries = firmware.parse_firmware_list(
            FIRMWARE_LIST.read_text(encoding="utf-8")
        )
        for entry in entries:
            with self.subTest(glob=entry.glob):
                self.assertIn(f"/usr/lib/firmware/{entry.glob}", paths)


if __name__ == "__main__":
    unittest.main()
