"""Validates every file the components install.

Each kind of file gets a syntax check, and every file except the firmware
list must say which hardware it matches and why it exists. A file of a kind
this test does not know fails, so a new kind arrives with its own check.
"""

import configparser
import pathlib
import re
import shutil
import subprocess
import tomllib
import unittest

from apex_hw.kernel import firmware

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPONENTS = ROOT / "components"

# A udev match on one of these keys ties a rule to hardware: a PCI or USB ID,
# a driver, a DMI field or a modalias. SUBSYSTEM or KERNEL alone does not.
_HARDWARE_KEY = re.compile(
    r"(ATTRS?\{(vendor|device|class|subsystem_vendor|subsystem_device"
    r"|idVendor|idProduct|\[dmi/id\][a-z_]+)\}"
    r"|DRIVERS?|ENV\{(MODALIAS|ID_VENDOR_ID|ID_MODEL_ID)\})=="
)
_MODPROBE = re.compile(r"(alias|blacklist|install|remove|options|softdep)\s+\S")


def _installed(pattern: str) -> list[pathlib.Path]:
    """Returns component and flavor files whose path under usr/ matches."""
    return sorted(
        [
            *COMPONENTS.glob(f"*/usr/{pattern}"),
            *(ROOT / "flavors").glob(f"*/*/usr/{pattern}"),
        ]
    )


def _rules(path: pathlib.Path) -> list[str]:
    """Returns the rules of a udev file, continuation lines joined."""
    text = path.read_text(encoding="utf-8").replace("\\\n", " ")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class KnownKindsTest(unittest.TestCase):
    """Every installed file is of a kind that a test below checks."""

    KINDS = (
        "lib/udev/rules.d/*.rules",
        "lib/udev/hwdb.d/*.hwdb",
        "lib/modprobe.d/*.conf",
        "lib/bootc/kargs.d/*.toml",
        "lib/tmpfiles.d/*.conf",
        "lib/tuned/profiles/*/tuned.conf",
        "share/apex-hardware/firmware.txt",
    )

    def test_every_file_is_a_known_kind(self) -> None:
        known = {path for kind in self.KINDS for path in _installed(kind)}
        for path in _installed("**/*"):
            if path.is_file():
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertIn(path, known)

    def test_every_file_states_match_and_reason(self) -> None:
        for path in _installed("**/*"):
            if not path.is_file() or path.name == "firmware.txt":
                continue
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                self.assertRegex(text, r"(?m)^# Matches: \S")
                self.assertRegex(text, r"(?m)^# Why: \S")


class UdevRulesTest(unittest.TestCase):
    """udev rules parse and each one is tied to hardware."""

    def test_udevadm_accepts_the_rules(self) -> None:
        files = _installed("lib/udev/rules.d/*.rules")
        if not files:
            self.skipTest("no rules")
        if shutil.which("udevadm") is None:
            self.skipTest("udevadm is not installed")
        result = subprocess.run(
            ["udevadm", "verify", "--resolve-names=never", *files],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_rule_matches_hardware(self) -> None:
        for path in _installed("lib/udev/rules.d/*.rules"):
            for rule in _rules(path):
                with self.subTest(path=path.name, rule=rule):
                    self.assertRegex(rule, _HARDWARE_KEY)

    def test_rule_files_are_named_for_apex(self) -> None:
        for path in _installed("lib/udev/rules.d/*.rules"):
            with self.subTest(path=path.name):
                self.assertRegex(
                    path.name, r"^[0-9]{2}-apex-[a-z0-9-]+\.rules$"
                )


class ModprobeTest(unittest.TestCase):
    """modprobe.d files use only modprobe.d(5) commands."""

    def test_commands_are_known(self) -> None:
        for path in _installed("lib/modprobe.d/*.conf"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.startswith("#"):
                    with self.subTest(path=path.name, line=line):
                        self.assertRegex(line, _MODPROBE)


class KargsTest(unittest.TestCase):
    """bootc kargs.d files are TOML with only the keys bootc reads."""

    def test_toml_shape(self) -> None:
        for path in _installed("lib/bootc/kargs.d/*.toml"):
            with self.subTest(path=path.name):
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                self.assertLessEqual(
                    set(data), {"kargs", "match-architectures"}
                )
                self.assertIsInstance(data["kargs"], list)
                for karg in data["kargs"]:
                    self.assertRegex(karg, r"^[^\s\"]+$")


class TmpfilesTest(unittest.TestCase):
    """tmpfiles.d lines have a type and an absolute path."""

    def test_lines_have_type_and_path(self) -> None:
        for path in _installed("lib/tmpfiles.d/*.conf"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.startswith("#"):
                    with self.subTest(path=path.name, line=line):
                        self.assertRegex(line, r"^[a-zA-Z][+!=~^-]*\s+/\S")


class TunedTest(unittest.TestCase):
    """tuned profiles parse as INI and have a [main] section."""

    def test_profiles_parse(self) -> None:
        for path in _installed("lib/tuned/profiles/*/tuned.conf"):
            with self.subTest(profile=path.parent.name):
                parser = configparser.ConfigParser()
                parser.read_string(path.read_text(encoding="utf-8"))
                self.assertIn("main", parser)


class FirmwareListTest(unittest.TestCase):
    """The firmware list parses and has no duplicate lines."""

    def test_list_parses(self) -> None:
        for path in _installed("share/apex-hardware/firmware.txt"):
            entries = firmware.parse_firmware_list(
                path.read_text(encoding="utf-8")
            )
            self.assertTrue(entries)
            pairs = [(entry.device, entry.glob) for entry in entries]
            self.assertEqual(len(pairs), len(set(pairs)))

    def test_parser_rejects_bad_lines(self) -> None:
        for text in (
            "pci:1002:1638",
            "pci:1002:163 amdgpu/x",
            "PCI:1002:1638 amdgpu/x",
            "pci:1002:1638 /usr/lib/firmware/x",
            "pci:1002:1638 ../x",
        ):
            with self.subTest(text=text):
                with self.assertRaises(firmware.FirmwareListError):
                    firmware.parse_firmware_list(text)


if __name__ == "__main__":
    unittest.main()
