"""CPU: frequency scaling, power profiles, suspend (s2idle) and resume."""

from collections.abc import Callable
import re

from apex_hw.checks import devices
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

ROW = "cpu"
_POLICY = "/sys/devices/system/cpu/cpufreq/policy0"
PROFILE_COMMAND = [
    "busctl",
    "get-property",
    "net.hadess.PowerProfiles",
    "/net/hadess/PowerProfiles",
    "net.hadess.PowerProfiles",
    "ActiveProfile",
]


def active_profile(output: str) -> str | None:
    """Parses busctl's 's "balanced"' into "balanced"."""
    found = re.fullmatch(r's "([^"]*)"', output.strip())
    return found.group(1) if found else None


# platform_profile values that match each power profile.
_PLATFORM = {
    "performance": ("performance",),
    "balanced": ("balanced",),
    "power-saver": ("low-power", "quiet"),
}


def probe_profile(wanted: str) -> Callable[[host_lib.Host], result.Result]:
    """Returns a check that a power profile is active and reached firmware.

    Args:
        wanted: "performance", "balanced" or "power-saver".
    """

    def probe(host: host_lib.Host) -> result.Result:
        done = host.run(PROFILE_COMMAND)
        active = active_profile(done.stdout) if done else None
        if active != wanted:
            return result.failed(ROW, f"active profile {active}, not {wanted}")
        platform = host.read("/sys/firmware/acpi/platform_profile")
        epp = host.read(f"{_POLICY}/energy_performance_preference")
        facts = f"profile {active}, EPP {epp}"
        if platform is None:
            return result.passed(ROW, f"{facts}, no platform_profile")
        if platform not in _PLATFORM[wanted]:
            return result.failed(
                ROW, f"{facts}, but platform_profile is {platform}"
            )
        return result.passed(ROW, f"{facts}, platform_profile {platform}")

    return probe


def probe_resumed(before: int) -> Callable[[host_lib.Host], result.Result]:
    """Returns a check that a suspend succeeded since `before` suspends.

    Args:
        before: The suspend count when the person was asked to suspend.
    """

    def probe(host: host_lib.Host) -> result.Result:
        after = devices.suspend_count(host)
        if after <= before:
            return result.failed(ROW, "no successful suspend was counted")
        hw_sleep = host.read("/sys/power/suspend_stats/last_hw_sleep")
        if hw_sleep == "0":
            return result.failed(ROW, "the s2idle never reached hardware sleep")
        slept = f", hardware sleep {hw_sleep} us" if hw_sleep else ""
        return result.passed(ROW, f"suspend {after} of this boot{slept}")

    return probe


def check(host: host_lib.Host) -> result.Result:
    """Checks the cpufreq driver, the power profile and system sleep."""
    problems: list[str] = []
    facts: list[str] = []

    scaling = host.read(f"{_POLICY}/scaling_driver")
    if scaling is None:
        problems.append("no cpufreq driver")
    else:
        governor = host.read(f"{_POLICY}/scaling_governor")
        epp = host.read(f"{_POLICY}/energy_performance_preference")
        facts.append(f"{scaling}, governor {governor}, EPP {epp}")

    done = host.run(PROFILE_COMMAND)
    profile = active_profile(done.stdout) if done else None
    if profile is None:
        problems.append("no power profile service on D-Bus")
    else:
        facts.append(f"profile {profile}")

    modes = host.read("/sys/power/mem_sleep") or ""
    if "s2idle" not in modes and "deep" not in modes:
        problems.append(f"no suspend mode offered ({modes or 'none'})")
    facts.append(f"mem_sleep {modes}")

    suspends = devices.suspend_count(host)
    failures = host.read("/sys/power/suspend_stats/fail") or "0"
    if failures != "0":
        problems.append(f"{failures} failed suspends this boot")
    hw_sleep = host.read("/sys/power/suspend_stats/last_hw_sleep")
    if suspends and hw_sleep == "0":
        problems.append("the last s2idle never reached hardware sleep")
    facts.append(f"{suspends} suspends, {failures} failed")
    if hw_sleep is not None:
        facts.append(f"last_hw_sleep {hw_sleep} us")
    return result.judge(ROW, problems, facts)
