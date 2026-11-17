"""Battery: a charge limit that UPower enforces and the firmware holds."""

import re

from apex_hw.checks import devices
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

ROW = "battery"
_DEVICE = "/org/freedesktop/UPower/devices/battery_{name}"


def busctl_value(output: str) -> str | None:
    """Parses busctl's "b true" or "u 80" into "true" or "80"."""
    found = re.fullmatch(r"[a-z] (\S+)", output.strip())
    return found.group(1) if found else None


def _property(host: host_lib.Host, name: str, prop: str) -> str | None:
    """Reads one UPower device property."""
    done = host.run(
        [
            "busctl",
            "get-property",
            "org.freedesktop.UPower",
            _DEVICE.format(name=name),
            "org.freedesktop.UPower.Device",
            prop,
        ]
    )
    if done is None or done.returncode != 0:
        return None
    return busctl_value(done.stdout)


def check(host: host_lib.Host) -> result.Result:
    """Checks the end threshold against UPower's limit."""
    batteries = [
        path
        for path in host.glob("/sys/class/power_supply/BAT*")
        if host.read(f"{path}/type") == "Battery"
    ]
    if not batteries:
        return result.absent(ROW, "no battery")
    battery = batteries[0]
    name = battery.rsplit("/", 1)[1]
    end = host.read(f"{battery}/charge_control_end_threshold")
    if end is None:
        return result.absent(ROW, f"{name} has no charge limit control")
    supported = _property(host, name, "ChargeThresholdSupported")
    enabled = _property(host, name, "ChargeThresholdEnabled")
    wanted = _property(host, name, "ChargeEndThreshold")
    problems: list[str] = []
    if supported != "true":
        problems.append("UPower does not support the limit")
    elif enabled != "true":
        problems.append("the limit is off in UPower")
    elif end != wanted:
        problems.append(f"sysfs end {end}, UPower wants {wanted}")
    if end == "100":
        problems.append("the battery charges to 100%")
    facts = [
        f"{name} end threshold {end}",
        f"UPower supported {supported}, enabled {enabled}, end {wanted}",
        f"{devices.suspend_count(host)} suspends this boot",
    ]
    return result.judge(ROW, problems, facts)
