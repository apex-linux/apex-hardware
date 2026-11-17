"""The outcome of one acceptance check."""

import dataclasses
import enum


class Status(enum.Enum):
    """How a check ended."""

    PASS = "pass"
    FAIL = "fail"
    ABSENT = "absent"


@dataclasses.dataclass(frozen=True)
class Result:
    """What a check found.

    Attributes:
        row: The row of the reference machine table, such as "dgpu".
        status: Pass, fail, or skipped because the hardware is absent.
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
