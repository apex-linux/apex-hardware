"""Built-in display: native mode at the highest refresh, scale, brightness."""

import dataclasses
import re

from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

ROW = "display"

# Panels whose default scale Apex sets, keyed by EDID vendor and product.
# The M7400QC's 14" 2880x1800 OLED is designed for scale 2.
EXPECTED_SCALE = {("SDC", "0x4154"): 2.0}

_MODE = re.compile(r"(\d+)x(\d+)@([\d.]+)")


@dataclasses.dataclass
class Monitor:
    """A monitor as gdctl reports it."""

    connector: str
    vendor: str = ""
    product: str = ""
    builtin: bool = False
    backlight: bool = False
    current: str = ""
    modes: list[str] = dataclasses.field(default_factory=list)
    scale: float | None = None


def parse_gdctl(text: str) -> list[Monitor]:
    """Parses `gdctl show --verbose`.

    Args:
        text: The command's output.

    Returns:
        The monitors, each with its logical monitor's scale.
    """
    monitors: dict[str, Monitor] = {}
    monitor: Monitor | None = None
    in_logical = False
    scale: float | None = None
    for raw in text.splitlines():
        line = raw.lstrip(" │├└─")
        if line.startswith("Logical monitors:"):
            in_logical = True
        elif not in_logical and line.startswith("Monitor "):
            monitor = Monitor(connector=line.split()[1])
            monitors[monitor.connector] = monitor
        elif in_logical and line.startswith("Scale:"):
            scale = float(line.split(":", 1)[1])
        elif in_logical and line.split(" ", 1)[0] in monitors:
            monitors[line.split(" ", 1)[0]].scale = scale
        elif monitor is not None and not in_logical:
            _monitor_line(monitor, line)
    return list(monitors.values())


def _monitor_line(monitor: Monitor, line: str) -> None:
    """Applies one line of a monitor's block."""
    if line.startswith("Vendor:"):
        monitor.vendor = line.split(":", 1)[1].strip()
    elif line.startswith("Product:"):
        monitor.product = line.split(":", 1)[1].strip()
    elif _MODE.fullmatch(line):
        monitor.modes.append(line)
    elif line.replace(" ", "") == "is-current⇒yes" and monitor.modes:
        monitor.current = monitor.modes[-1]
    elif line.replace(" ", "") == "is-builtin⇒yes":
        monitor.builtin = True
    elif line.replace(" ", "") == "active⇒True":
        monitor.backlight = True


def best_mode(modes: list[str]) -> str:
    """Returns the largest mode at its highest refresh rate."""

    def key(mode: str) -> tuple[int, float]:
        found = _MODE.fullmatch(mode)
        assert found is not None
        width, height, rate = found.groups()
        return int(width) * int(height), float(rate)

    return max(modes, key=key)


def check(host: host_lib.Host) -> result.Result:
    """Checks the built-in panel's mode, scale and backlight."""
    panels = [
        path
        for path in host.glob("/sys/class/drm/card*-*/status")
        if re.search(r"-(eDP|LVDS|DSI)-", path)
        and host.read(path) == "connected"
    ]
    if not panels:
        return result.absent(ROW, "no built-in panel")
    done = host.run(["gdctl", "show", "--verbose"])
    if done is None or done.returncode != 0:
        return result.failed(ROW, "gdctl failed: run in a GNOME session")
    builtin = [m for m in parse_gdctl(done.stdout) if m.builtin]
    if not builtin or not builtin[0].modes:
        return result.failed(ROW, "mutter reports no built-in monitor")
    panel = builtin[0]
    problems: list[str] = []
    best = best_mode(panel.modes)
    if panel.current != best:
        problems.append(f"mode {panel.current}, best is {best}")
    expected = EXPECTED_SCALE.get((panel.vendor, panel.product))
    if expected is not None and panel.scale != expected:
        problems.append(f"scale {panel.scale}, Apex default is {expected}")
    if not panel.backlight and not host.glob("/sys/class/backlight/*"):
        problems.append("no backlight control")
    facts = [
        f"{panel.connector} {panel.vendor} {panel.product}",
        f"mode {panel.current}",
        f"scale {panel.scale}",
        f"backlight {'yes' if panel.backlight else 'sysfs only'}",
    ]
    return result.judge(ROW, problems, facts)
