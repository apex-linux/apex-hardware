"""Analog audio codec and HDMI audio.

The analog check reads the codec's pin configuration, which says what the
firmware wired up, and then PipeWire's routes, which say what the desktop
offers. Whether sound comes out right is a listening test (see docs).
"""

import json
import os
from typing import Any

from apex_hw.checks import devices
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

ROW = "audio"
HDMI_ROW = "hdmi_audio"

# HD audio pin default configuration (HDA specification 7.3.3.31).
_FIXED = 2
_DEVICE_NAMES = {0x1: "speaker", 0x2: "headphone", 0xA: "mic"}


def pins(init: str, override: str = "") -> dict[int, int]:
    """Parses init_pin_configs, with driver_pin_configs taking precedence."""
    table: dict[int, int] = {}
    for text in (init, override):
        for line in text.splitlines():
            fields = line.split()
            if len(fields) == 2:
                table[int(fields[0], 16)] = int(fields[1], 16)
    return table


def endpoints(table: dict[int, int]) -> set[str]:
    """Names the wired endpoints: "speaker", "headphone jack", "internal mic".

    A pin counts when its port connectivity is a jack or fixed; fixed
    speakers and mics are internal, jacks are external.
    """
    found = set()
    for config in table.values():
        connectivity = config >> 30
        kind = _DEVICE_NAMES.get((config >> 20) & 0xF)
        if connectivity == 1 or kind is None:
            continue
        place = "internal" if connectivity == _FIXED else "jack"
        found.add(f"{place} {kind}")
    return found


def _codecs(host: host_lib.Host, hdmi: bool) -> list[str]:
    """Returns hwdep directories of analog or HDMI codecs."""
    found = []
    for path in host.glob("/sys/class/sound/hwC*D*"):
        name = host.read(f"{path}/chip_name") or ""
        if ("HDMI" in name or "DisplayPort" in name) == hdmi:
            found.append(path)
    return found


def pipewire_routes(text: str) -> set[str]:
    """Returns the route names of ALSA devices in `pw-dump` output."""
    routes = set()
    objects: list[dict[str, Any]] = json.loads(text)
    for item in objects:
        if item.get("type") != "PipeWire:Interface:Device":
            continue
        params = (item.get("info") or {}).get("params") or {}
        for route in params.get("EnumRoute") or []:
            routes.add(str(route.get("name")))
    return routes


def available_routes(text: str) -> set[str]:
    """Returns the routes that PipeWire marks available, such as a jack
    with something plugged in."""
    routes = set()
    objects: list[dict[str, Any]] = json.loads(text)
    for item in objects:
        if item.get("type") != "PipeWire:Interface:Device":
            continue
        params = (item.get("info") or {}).get("params") or {}
        for route in params.get("EnumRoute") or []:
            if route.get("available") == "yes":
                routes.add(str(route.get("name")))
    return routes


def probe_headphones(host: host_lib.Host) -> result.Result:
    """Checks that PipeWire sees headphones in the jack."""
    dump = host.run(["pw-dump"])
    if dump is None or dump.returncode != 0:
        return result.failed(ROW, "PipeWire not reachable")
    if "analog-output-headphones" not in available_routes(dump.stdout):
        return result.failed(ROW, "PipeWire sees nothing in the headphone jack")
    return result.passed(ROW, "headphones detected in the jack")


def check(host: host_lib.Host) -> result.Result:
    """Checks speakers, headphone jack and internal microphone."""
    codecs = _codecs(host, hdmi=False)
    if not codecs:
        return result.absent(ROW, "no analog HD audio codec")
    codec = codecs[0]
    name = host.read(f"{codec}/chip_name")
    subsystem = host.read(f"{codec}/subsystem_id")
    table = pins(
        host.read(f"{codec}/init_pin_configs") or "",
        host.read(f"{codec}/driver_pin_configs") or "",
    )
    wired = endpoints(table)
    problems = [
        f"no {want} pin"
        for want in ("internal speaker", "jack headphone", "internal mic")
        if want not in wired
    ]
    facts = [f"{name} {subsystem}", "pins " + ", ".join(sorted(wired))]
    dump = host.run(["pw-dump"])
    if dump is None or dump.returncode != 0:
        facts.append("PipeWire not reachable")
    else:
        routes = pipewire_routes(dump.stdout)
        for want in ("analog-output-speaker", "analog-output-headphones"):
            if want not in routes:
                problems.append(f"PipeWire has no {want}")
        if not any(route.startswith("analog-input") for route in routes):
            problems.append("PipeWire has no analog input")
        facts.append("routes " + ", ".join(sorted(routes)))
    fixups = devices.kernel_log(host, "picked fixup|patch firmware")
    if fixups is not None:
        facts.append(f"{len(fixups)} quirk lines in the kernel log")
    return result.judge(ROW, problems, facts)


def probe_hdmi_monitor(host: host_lib.Host) -> result.Result:
    """Checks that a display that takes audio is connected over HDMI."""
    return check_hdmi(host, need_monitor=True)


def check_hdmi(
    host: host_lib.Host, need_monitor: bool = False
) -> result.Result:
    """Checks that an HDMI audio codec is probed with playback devices.

    Args:
        host: The machine.
        need_monitor: Also require a connected monitor that takes audio.
    """
    codecs = _codecs(host, hdmi=True)
    if not codecs:
        return result.absent(HDMI_ROW, "no HDMI audio codec")
    codec = codecs[0]
    card = os.path.basename(codec)[3:].split("D")[0]
    controller = devices.owning_device(host, f"/sys/class/sound/card{card}")
    problems: list[str] = []
    if controller is None or not controller.driver:
        problems.append("controller has no driver")
    playback = host.glob(f"/proc/asound/card{card}/pcm*p")
    if not playback:
        problems.append("no playback devices")
    present = 0
    for eld in host.glob(f"/proc/asound/card{card}/eld#*"):
        if "monitor_present\t\t1" in (host.read(eld) or ""):
            present += 1
    if need_monitor and not present:
        problems.append("no monitor with audio is connected")
    ident = controller.ident if controller else "unknown"
    facts = [
        f"{ident} {host.read(f'{codec}/chip_name')}",
        f"{len(playback)} playback devices",
        f"{present} monitors with audio connected",
    ]
    return result.judge(HDMI_ROW, problems, facts)
