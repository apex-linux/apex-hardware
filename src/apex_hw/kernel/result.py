"""The outcome of one acceptance check."""

from collections.abc import Sequence
import dataclasses
import enum


class Status(enum.Enum):
    """How a check ended."""

    PASS = "pass"
    FAIL = "fail"
    ABSENT = "absent"
    NEEDS_PERSON = "needs_person"


@dataclasses.dataclass(frozen=True)
class Result:
    """What a check found.

    Attributes:
        row: The row of the reference machine table, such as "dgpu".
        status: Pass, fail, needs a person, or skipped because the hardware
            is absent.
        value: The measured values, or why it failed, in one line.
    """

    row: str
    status: Status
    value: str


def passed(row: str, value: str) -> Result:
    """Returns a passing result."""
    return Result(row, Status.PASS, value)


def failed(row: str, value: str) -> Result:
    """Returns a failing result."""
    return Result(row, Status.FAIL, value)


def absent(row: str, value: str) -> Result:
    """Returns the result for hardware that this machine does not have."""
    return Result(row, Status.ABSENT, value)


def needs_person(row: str, value: str) -> Result:
    """Returns the result for a part that only a person can judge."""
    return Result(row, Status.NEEDS_PERSON, value)


def judge(row: str, problems: list[str], facts: list[str]) -> Result:
    """Passes when there are no problems; reports problems first.

    Args:
        row: The row name.
        problems: What is wrong, empty when the check passes.
        facts: What was measured.

    Returns:
        A pass or a fail with the problems and facts joined.
    """
    value = "; ".join(problems + facts)
    return failed(row, value) if problems else passed(row, value)


@dataclasses.dataclass(frozen=True)
class Evidence:
    """One part of a row's verdict.

    Attributes:
        step: What produced it: "automated", "after resume", or the name of
            a guided step such as "speakers".
        status: That part's outcome.
        value: What was measured or answered, in one line.
    """

    step: str
    status: Status
    value: str


@dataclasses.dataclass(frozen=True)
class RowRecord:
    """A row's verdict and the evidence behind it."""

    result: Result
    evidence: tuple[Evidence, ...]


def combine(row: str, evidence: Sequence[Evidence]) -> Result:
    """Turns a row's evidence into its verdict.

    The first item is the automated check. The row is absent when that is;
    otherwise it fails when any part fails, needs a person when any part is
    still unanswered, and passes only when every part passed.

    Args:
        row: The row name.
        evidence: The automated check first, then the other parts.

    Returns:
        The row's result, its value led by what decided it.
    """
    automated = evidence[0]
    if automated.status is Status.ABSENT:
        return absent(row, automated.value)
    others = evidence[1:]
    failing = [e for e in others if e.status is Status.FAIL]
    if automated.status is Status.FAIL or failing:
        parts = [automated.value] if automated.status is Status.FAIL else []
        parts += [f"{e.step}: {e.value}" for e in failing]
        if automated.status is not Status.FAIL:
            parts.append(automated.value)
        return failed(row, "; ".join(parts))
    waiting = [e.step for e in others if e.status is Status.NEEDS_PERSON]
    if waiting:
        return needs_person(
            row, f"{automated.value}; needs a person: {', '.join(waiting)}"
        )
    confirmed = [e.step for e in others]
    if confirmed:
        return passed(
            row, f"{automated.value}; confirmed: {', '.join(confirmed)}"
        )
    return passed(row, automated.value)
