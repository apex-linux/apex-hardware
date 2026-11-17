"""A Person for tests that answers from a script."""

from collections.abc import Callable, Iterable


class ScriptedPerson:
    """Answers waits and questions in order, and records what it was shown.

    Each answer is True (done, or yes), False (skipped wait, or no) or None
    (skipped question). Before each answer it calls `act`, so a test can
    change the fake machine the way the person's action would.
    """

    def __init__(
        self,
        answers: Iterable[bool | None],
        act: Callable[[str], None] | None = None,
    ) -> None:
        self._answers = list(answers)
        self._act = act
        self.shown: list[str] = []

    def _next(self, prompt: str) -> bool | None:
        """Returns the next scripted answer; running out skips."""
        self.shown.append(prompt)
        if self._act is not None:
            self._act(prompt)
        return self._answers.pop(0) if self._answers else None

    def tell(self, text: str) -> None:
        """Records instructions."""
        self.shown.append(text)

    def wait(self, prompt: str) -> bool:
        """Returns the next answer as done or skipped."""
        return bool(self._next(prompt))

    def ask(self, question: str) -> bool | None:
        """Returns the next answer."""
        return self._next(question)
