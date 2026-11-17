"""The port through which a guided run talks to the person at the machine.

Some rows need hands on the machine: a finger on the reader, an ear at the
speaker, a cable in the HDMI port. A guided step tells the person what to
do and asks one yes-or-no question about what happened.
"""

from typing import Protocol, TextIO

_YES = ("y", "yes")
_NO = ("n", "no")
_SKIP = ("s", "skip")


class Person(Protocol):
    """Someone who can act on the machine and answer questions."""

    def tell(self, text: str) -> None:
        """Shows instructions."""

    def wait(self, prompt: str) -> bool:
        """Waits until the person has acted; False when they skipped."""

    def ask(self, question: str) -> bool | None:
        """Asks a yes-or-no question; None when they skipped it."""


class NoPerson:
    """Nobody at the machine: every guided step stays unanswered."""

    # mypy requires the return in ask() that pylint calls useless.
    # pylint: disable=useless-return

    def tell(self, text: str) -> None:
        """Shows nothing."""
        del text

    def wait(self, prompt: str) -> bool:
        """Returns False: nobody acted."""
        del prompt
        return False

    def ask(self, question: str) -> bool | None:
        """Returns None: nobody answered."""
        del question
        return None


class TerminalPerson:
    """A person at a terminal.

    Prompts go to the error stream so that standard output stays the
    report, also when it is JSON. End of input skips every step left.
    """

    def __init__(self, stdin: TextIO, stderr: TextIO) -> None:
        self._stdin = stdin
        self._stderr = stderr
        self._closed = False

    def _line(self, prompt: str) -> str | None:
        """Reads one answer; None at end of input."""
        if self._closed:
            return None
        self._stderr.write(prompt)
        self._stderr.flush()
        line = self._stdin.readline()
        if not line:
            self._closed = True
            self._stderr.write("\n")
            return None
        return line.strip().lower()

    def tell(self, text: str) -> None:
        """Shows instructions."""
        if not self._closed:
            self._stderr.write(f"\n{text}\n")

    def wait(self, prompt: str) -> bool:
        """Waits for Enter; "s" skips."""
        answer = self._line(f"{prompt} [Enter when done, s to skip] ")
        return answer is not None and answer not in _SKIP

    def ask(self, question: str) -> bool | None:
        """Asks until the answer is yes, no or skip."""
        while True:
            answer = self._line(f"{question} [y/n/s] ")
            if answer is None or answer in _SKIP:
                return None
            if answer in _YES:
                return True
            if answer in _NO:
                return False
