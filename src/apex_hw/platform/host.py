"""The port through which checks read the machine, and its Linux adapter.

Checks only read. None of these methods writes to the system, and the
Linux adapter never reads PCI configuration space, which would wake a
runtime-suspended device.
"""

from collections.abc import Sequence
import dataclasses
import glob
import os
import shutil
import subprocess
import time
from typing import Protocol


@dataclasses.dataclass(frozen=True)
class Command:
    """The outcome of a command.

    Attributes:
        returncode: The exit status.
        stdout: Standard output as text.
    """

    returncode: int
    stdout: str


class Host(Protocol):
    """Read-only access to a running system."""

    def read(self, path: str) -> str | None:
        """Returns a file's text without trailing whitespace, or None."""

    def read_bytes(self, path: str) -> bytes | None:
        """Returns a file's bytes, or None."""

    def glob(self, pattern: str) -> list[str]:
        """Returns the sorted paths that match a glob."""

    def readlink(self, path: str) -> str | None:
        """Returns a symbolic link's target, or None."""

    def realpath(self, path: str) -> str:
        """Returns the path with every symbolic link resolved."""

    def access(self, path: str, mode: int) -> bool:
        """Returns whether this user may access a path with os.access mode."""

    def run(self, argv: Sequence[str]) -> Command | None:
        """Runs a command; returns None if it is not installed or hangs."""

    def env(self, name: str) -> str | None:
        """Returns an environment variable, or None."""

    def sleep(self, seconds: float) -> None:
        """Waits."""


class LinuxHost:
    """Reads the machine this program runs on."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def read(self, path: str) -> str | None:
        """Returns a file's text without trailing whitespace, or None."""
        try:
            with open(path, encoding="utf-8", errors="replace") as file:
                return file.read().rstrip()
        except OSError:
            return None

    def read_bytes(self, path: str) -> bytes | None:
        """Returns a file's bytes, or None."""
        try:
            with open(path, "rb") as file:
                return file.read()
        except OSError:
            return None

    def glob(self, pattern: str) -> list[str]:
        """Returns the sorted paths that match a glob."""
        return sorted(glob.glob(pattern))

    def readlink(self, path: str) -> str | None:
        """Returns a symbolic link's target, or None."""
        try:
            return os.readlink(path)
        except OSError:
            return None

    def realpath(self, path: str) -> str:
        """Returns the path with every symbolic link resolved."""
        return os.path.realpath(path)

    def access(self, path: str, mode: int) -> bool:
        """Returns whether this user may access a path with os.access mode."""
        return os.access(path, mode)

    def run(self, argv: Sequence[str]) -> Command | None:
        """Runs a command; returns None if it is not installed or hangs."""
        if shutil.which(argv[0]) is None:
            return None
        try:
            done = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
                env={**os.environ, "LC_ALL": "C"},
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return Command(done.returncode, done.stdout)

    def env(self, name: str) -> str | None:
        """Returns an environment variable, or None."""
        return os.environ.get(name)

    def sleep(self, seconds: float) -> None:
        """Waits."""
        time.sleep(seconds)
