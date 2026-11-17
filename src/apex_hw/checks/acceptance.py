"""One acceptance run: automated checks, a suspend, then guided steps.

The order matters. The automated checks run first, from an idle machine,
because the discrete GPU's reading must not follow anything that woke it.
The suspend comes next so that every guided step after it also runs on a
resumed machine. Each row's verdict combines all of its evidence.
"""

from collections.abc import Sequence
import dataclasses

from apex_hw.checks import cpu
from apex_hw.checks import devices
from apex_hw.checks import guides
from apex_hw.checks import network
from apex_hw.checks import registry
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib
from apex_hw.platform import person as person_lib

Evidence = result.Evidence
Status = result.Status

# How long a row may take to recover after a resume, in seconds.
_SETTLE = {network.WIFI_ROW: 30}
_SETTLE_STEP = 3

INTRO = (
    "Some rows need you at the machine. Each step says what to do, then"
    " asks one question: answer y or n, or s to skip it. A skipped step"
    " leaves its row unfinished, not failed."
)


@dataclasses.dataclass(frozen=True)
class RowRecord:
    """A row's verdict and the evidence behind it."""

    result: result.Result
    evidence: tuple[Evidence, ...]


def _safe(check: guides.Probe, row: str, host: host_lib.Host) -> result.Result:
    """Runs a check; a crash fails it instead of the whole run."""
    try:
        return check(host)
    except Exception as error:  # pylint: disable=broad-exception-caught
        return result.failed(row, f"check crashed: {error!r}")


def _settled(
    check: guides.Probe, row: str, host: host_lib.Host
) -> result.Result:
    """Runs a check, retrying a failure while the row may still recover."""
    checked = _safe(check, row, host)
    waited = 0
    while checked.status is Status.FAIL and waited < _SETTLE.get(row, 0):
        host.sleep(_SETTLE_STEP)
        waited += _SETTLE_STEP
        checked = _safe(check, row, host)
    return checked


def _step(
    row: str,
    step: guides.Step,
    host: host_lib.Host,
    person: person_lib.Person,
) -> Evidence:
    """Guides the person through one step and judges it."""
    person.tell(f"[{row}] {step.name}\n{step.do}")
    facts = ""
    if step.probe is not None:
        if not person.wait("Do it now."):
            return Evidence(step.name, Status.NEEDS_PERSON, "not done")
        probed = _safe(step.probe, row, host)
        if probed.status is not Status.PASS:
            return Evidence(step.name, Status.FAIL, probed.value)
        if step.ask is None:
            return Evidence(step.name, Status.PASS, probed.value)
        facts = f"{probed.value}; "
    assert step.ask is not None
    answer = person.ask(step.ask)
    if answer is None:
        return Evidence(
            step.name, Status.NEEDS_PERSON, f"{facts}not answered: {step.ask}"
        )
    status = Status.PASS if answer else Status.FAIL
    return Evidence(
        step.name, status, f"{facts}{'yes' if answer else 'no'}: {step.ask}"
    )


def _resume(
    checks: dict[str, guides.Probe],
    automated: dict[str, result.Result],
    host: host_lib.Host,
    person: person_lib.Person,
) -> dict[str, list[Evidence]]:
    """Returns each resume row's evidence from after a suspend.

    A suspend earlier in this boot already makes the automated readings
    post-resume ones. Otherwise the person is asked to suspend now, and the
    rows are measured again once the machine is back.
    """
    rows = [
        row
        for row in guides.RESUME_ROWS
        if row in automated and automated[row].status is not Status.ABSENT
    ]
    if not rows:
        return {}
    before = devices.suspend_count(host)
    if before:
        note = f"measured after suspend {before} of this boot"
        return {
            row: [Evidence("after resume", Status.PASS, note)]
            for row in rows
            if automated[row].status is Status.PASS
        }
    person.tell(f"[suspend] {guides.SUSPEND_NAME}\n{guides.SUSPEND_DO}")
    if not person.wait("Suspend and wake the machine now."):
        return {
            row: [
                Evidence(
                    "after resume",
                    Status.NEEDS_PERSON,
                    "no suspend in this boot",
                )
            ]
            for row in rows
        }
    resumed = _safe(cpu.probe_resumed(before), cpu.ROW, host)
    found: dict[str, list[Evidence]] = {
        cpu.ROW: [Evidence(guides.SUSPEND_NAME, resumed.status, resumed.value)]
    }
    for row in rows:
        if resumed.status is not Status.PASS:
            again = Evidence(
                "after resume", Status.NEEDS_PERSON, "the suspend failed"
            )
        else:
            measured = _settled(checks[row], row, host)
            again = Evidence("after resume", measured.status, measured.value)
        found.setdefault(row, []).append(again)
    return found


def run(
    checks: Sequence[tuple[str, registry.Check]],
    host: host_lib.Host,
    person: person_lib.Person,
) -> list[RowRecord]:
    """Runs the checks, the suspend and the guided steps for these rows.

    Args:
        checks: (row, check) pairs in the order they run.
        host: The machine.
        person: Who acts and answers; NoPerson leaves every guided step
            unanswered, so those rows need a person.

    Returns:
        One record per row, in the order of `checks`.
    """
    by_row = dict(checks)
    automated = {row: _safe(check, row, host) for row, check in checks}
    person.tell(INTRO)
    resumed = _resume(by_row, automated, host, person)
    records = []
    for row, _ in checks:
        first = automated[row]
        evidence = [Evidence("automated", first.status, first.value)]
        if first.status is not Status.ABSENT:
            evidence += resumed.get(row, [])
            if first.status is Status.PASS:
                evidence += [
                    _step(row, step, host, person)
                    for step in guides.GUIDES.get(row, ())
                ]
        records.append(
            RowRecord(result.combine(row, evidence), tuple(evidence))
        )
    return records
