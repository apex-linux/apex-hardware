"""Input: internal keyboard, multi-finger touchpad, backlight, hotkeys."""

import dataclasses
import re

from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

ROW = "input"

_BTN_TOOL_TRIPLETAP = 0x14E
_ABS_MT_POSITION_X = 0x35
# Vendor drivers that turn function keys into input events.
_HOTKEYS = re.compile(
    r"WMI hotkeys|Extra Buttons|Intel HID events|Ideapad extra buttons"
    r"|ThinkPad Extra Buttons|Dell WMI hotkeys|HP WMI hotkeys"
)


@dataclasses.dataclass
class InputDevice:
    """One block of /proc/bus/input/devices."""

    name: str = ""
    phys: str = ""
    bits: dict[str, int] = dataclasses.field(default_factory=dict)

    def has(self, kind: str, bit: int) -> bool:
        """Returns whether a capability bitmap ("KEY", "ABS") has a bit."""
        return bool(self.bits.get(kind, 0) >> bit & 1)


def parse_devices(text: str) -> list[InputDevice]:
    """Parses /proc/bus/input/devices."""
    found = []
    for block in text.split("\n\n"):
        device = InputDevice()
        for line in block.splitlines():
            if line.startswith("N: Name="):
                device.name = line[8:].strip('"')
            elif line.startswith("P: Phys="):
                device.phys = line[8:]
            elif line.startswith("B: "):
                kind, _, words = line[3:].partition("=")
                # Words are 64-bit hex, most significant first.
                value = 0
                for word in words.split():
                    value = value << 64 | int(word, 16)
                device.bits[kind] = value
        if device.name:
            found.append(device)
    return found


def check(host: host_lib.Host) -> result.Result:
    """Checks the internal keyboard, touchpad gestures, backlight, hotkeys."""
    found = parse_devices(host.read("/proc/bus/input/devices") or "")
    keyboards = [d for d in found if d.phys.startswith("isa0060/serio0")]
    touchpads = [
        d
        for d in found
        if d.has("ABS", _ABS_MT_POSITION_X) and "Touchpad" in d.name
    ]
    if not keyboards and not touchpads:
        return result.absent(ROW, "no internal keyboard or touchpad")
    problems: list[str] = []
    facts: list[str] = []
    if not keyboards:
        problems.append("no internal keyboard")
    if not touchpads:
        problems.append("no multitouch touchpad")
    elif not touchpads[0].has("KEY", _BTN_TOOL_TRIPLETAP):
        problems.append("touchpad reports fewer than three fingers")
    else:
        facts.append(f"touchpad {touchpads[0].name}, three-finger gestures")
    hotkeys = [d.name for d in found if _HOTKEYS.search(d.name)]
    if not hotkeys:
        problems.append("no vendor hotkey device")
    else:
        facts.append(f"hotkeys {hotkeys[0]}")
    leds = host.glob("/sys/class/leds/*::kbd_backlight")
    if leds:
        top = host.read(f"{leds[0]}/max_brightness")
        facts.append(f"keyboard backlight {leds[0].rsplit('/', 1)[1]} 0-{top}")
    else:
        facts.append("no keyboard backlight")
    return result.judge(ROW, problems, facts)
