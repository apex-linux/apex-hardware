"""Tests the order and the verdicts of a whole acceptance run."""

import unittest

from apex_hw.checks import acceptance
from apex_hw.checks import guides
from apex_hw.checks import registry
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib
from apex_hw.platform import person
from apex_hw.testkit.fake_host import FakeHost
from apex_hw.testkit.scripted_person import ScriptedPerson

Status = result.Status
SUCCESS = "/sys/power/suspend_stats/success"


def _fixed(row: str, status: Status) -> registry.Check:
    def check(host: host_lib.Host) -> result.Result:
        del host
        return result.Result(row, status, f"{row} measured")

    return check


def _wifi(host: host_lib.Host) -> result.Result:
    """Fails until the fake link comes back."""
    if host.read("/fake/wifi") == "up":
        return result.passed("wifi", "connected")
    return result.failed("wifi", "disconnected")


def _host(suspends: str = "0") -> FakeHost:
    return FakeHost(
        files={
            SUCCESS: suspends,
            "/sys/power/suspend_stats/last_hw_sleep": "5",
            "/fake/wifi": "up",
        }
    )


class _ReconnectingHost(FakeHost):
    """A machine whose Wi-Fi comes back after the first wait."""

    def __init__(self) -> None:
        super().__init__(_host().files)

    def sleep(self, seconds: float) -> None:
        super().sleep(seconds)
        self.files["/fake/wifi"] = "up"


class RunTest(unittest.TestCase):

    def test_without_a_person_guided_rows_need_one(self) -> None:
        checks = [
            ("igpu", _fixed("igpu", Status.PASS)),
            ("display", _fixed("display", Status.PASS)),
        ]
        records = acceptance.run(checks, _host(), person.NoPerson())
        self.assertEqual(
            [r.result.status for r in records],
            [Status.PASS, Status.NEEDS_PERSON],
        )
        self.assertIn("needs a person: brightness", records[1].result.value)

    def test_a_suspend_earlier_this_boot_counts_as_resume(self) -> None:
        checks = [("wifi", _wifi)]
        records = acceptance.run(checks, _host("2"), person.NoPerson())
        self.assertIs(records[0].result.status, Status.PASS)
        self.assertEqual(
            [e.step for e in records[0].evidence], ["automated", "after resume"]
        )

    def test_without_any_suspend_resume_rows_need_a_person(self) -> None:
        checks = [("wifi", _wifi)]
        records = acceptance.run(checks, _host(), person.NoPerson())
        self.assertIs(records[0].result.status, Status.NEEDS_PERSON)

    def test_guided_suspend_measures_again_after_resume(self) -> None:
        host = _ReconnectingHost()

        def act(prompt: str) -> None:
            if prompt.startswith("Suspend"):
                host.files[SUCCESS] = "1"
                host.files["/fake/wifi"] = "down"

        checks = [
            ("cpu", _fixed("cpu", Status.PASS)),
            ("wifi", _wifi),
        ]
        records = acceptance.run(
            checks, host, ScriptedPerson([True, True], act)
        )
        cpu, wifi = records[0], records[1]
        self.assertEqual(
            [e.step for e in cpu.evidence],
            [
                "automated",
                guides.SUSPEND_NAME,
                "after resume",
                "power profiles",
            ],
        )
        self.assertIs(cpu.result.status, Status.PASS, cpu.result.value)
        self.assertIs(wifi.result.status, Status.PASS, wifi.result.value)
        self.assertEqual(host.slept, 3)

    def test_a_suspend_that_did_not_happen_fails_cpu(self) -> None:
        checks = [("cpu", _fixed("cpu", Status.PASS))]
        records = acceptance.run(checks, _host(), ScriptedPerson([True]))
        self.assertIs(records[0].result.status, Status.FAIL)
        self.assertIn("no successful suspend", records[0].result.value)

    def test_a_failing_probe_does_not_ask(self) -> None:
        def offload_probe_fails(host: host_lib.Host) -> result.Result:
            del host
            return result.failed("dgpu", "runtime status suspended")

        step = guides.Step("x", "do", ask="ok?", probe=offload_probe_fails)
        at = ScriptedPerson([True, True])
        # pylint: disable-next=protected-access
        found = acceptance._step("dgpu", step, _host(), at)
        self.assertIs(found.status, Status.FAIL)
        self.assertNotIn("ok?", at.shown)

    def test_failed_rows_are_not_guided(self) -> None:
        checks = [("audio", _fixed("audio", Status.FAIL))]
        at = ScriptedPerson([])
        records = acceptance.run(checks, _host(), at)
        self.assertEqual(len(records[0].evidence), 1)
        self.assertFalse(any("speakers" in s for s in at.shown))

    def test_absent_rows_are_not_guided(self) -> None:
        checks = [("audio", _fixed("audio", Status.ABSENT))]
        records = acceptance.run(checks, _host(), ScriptedPerson([True] * 9))
        self.assertIs(records[0].result.status, Status.ABSENT)

    def test_every_answer_yes_passes(self) -> None:
        checks = [("display", _fixed("display", Status.PASS))]
        records = acceptance.run(checks, _host(), ScriptedPerson([True]))
        self.assertIs(records[0].result.status, Status.PASS)
        self.assertIn("confirmed: brightness", records[0].result.value)


class GuidesTest(unittest.TestCase):

    def test_every_step_is_judged(self) -> None:
        for row, steps in guides.GUIDES.items():
            for step in steps:
                with self.subTest(row=row, step=step.name):
                    self.assertTrue(step.ask or step.probe)
                    self.assertTrue(step.do)

    def test_guides_and_resume_rows_name_real_rows(self) -> None:
        rows = {row for row, _ in registry.all_checks("firmware.txt")}
        self.assertLessEqual(set(guides.GUIDES), rows)
        self.assertLessEqual(set(guides.RESUME_ROWS), rows)

    def test_only_these_rows_are_judged_by_programs_alone(self) -> None:
        rows = {row for row, _ in registry.all_checks("firmware.txt")}
        alone = rows - set(guides.GUIDES) - set(guides.RESUME_ROWS)
        self.assertEqual(alone, {"igpu", "storage", "firmware"})


if __name__ == "__main__":
    unittest.main()
