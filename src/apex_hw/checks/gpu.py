"""Integrated and discrete GPUs.

The GPU the firmware booted on (boot_vga) is the integrated one on a
hybrid laptop; every other display controller counts as discrete.
"""

from apex_hw.checks import devices
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

IGPU_ROW = "igpu"
DGPU_ROW = "dgpu"
_SETTLE_SECONDS = 15


def _split(
    host: host_lib.Host,
) -> tuple[list[devices.Device], list[devices.Device]]:
    """Returns (boot GPUs, other GPUs)."""
    boot, other = [], []
    for gpu in devices.pci_devices(host, "03"):
        if host.read(f"{gpu.path}/boot_vga") == "1":
            boot.append(gpu)
        else:
            other.append(gpu)
    return boot, other


def check_igpu(host: host_lib.Host) -> result.Result:
    """Checks that the boot GPU has a driver and lights a display."""
    boot, _ = _split(host)
    if not boot:
        return result.absent(IGPU_ROW, "no boot VGA device")
    gpu = boot[0]
    problems: list[str] = []
    facts = [f"{gpu.ident} {gpu.driver or 'no driver'}"]
    if not gpu.driver:
        problems.append("no driver bound")
    connected = [
        path.rsplit("/", 2)[-2].split("-", 1)[1]
        for path in host.glob(f"{gpu.path}/drm/card*/card*-*/status")
        if host.read(path) == "connected"
    ]
    if not connected:
        problems.append("no connected display")
    facts.append("connected " + (", ".join(connected) or "none"))
    session = host.env("XDG_SESSION_TYPE")
    if session is not None and session != "wayland":
        problems.append(f"session is {session}, not wayland")
    facts.append(f"session {session or 'unknown (not run in a session)'}")
    return result.judge(IGPU_ROW, problems, facts)


def _share(host: host_lib.Host, path: str) -> str:
    """Returns the runtime-suspended share since boot as a percentage."""
    try:
        down = int(host.read(f"{path}/power/runtime_suspended_time") or "0")
        up = int(host.read(f"{path}/power/runtime_active_time") or "0")
    except ValueError:
        return "unknown"
    return f"{100 * down / (down + up):.1f}%" if down + up else "unknown"


def check_dgpu(host: host_lib.Host) -> result.Result:
    """Checks that the discrete GPU is runtime-suspended in D3cold.

    It reads only power attributes, so it never wakes the GPU itself. It
    waits up to fifteen seconds for the GPU to suspend after a recent use.
    """
    _, other = _split(host)
    if not other:
        return result.absent(DGPU_ROW, "no second GPU")
    gpu = other[0]
    status = host.read(f"{gpu.path}/power/runtime_status")
    for _ in range(_SETTLE_SECONDS):
        if status == "suspended":
            break
        host.sleep(1)
        status = host.read(f"{gpu.path}/power/runtime_status")
    control = host.read(f"{gpu.path}/power/control")
    state = host.read(f"{gpu.path}/power_state")
    problems: list[str] = []
    if control != "auto":
        problems.append(f"power/control is {control}")
    if status != "suspended":
        problems.append(f"runtime status is {status}")
    if state is not None and state != "D3cold":
        problems.append(f"power state is {state}")
    facts = [
        f"{gpu.ident} {gpu.driver or 'no driver'}",
        f"control {control}, {status}, {state or 'no power_state'}",
        f"suspended {_share(host, gpu.path)} of the time since boot",
    ]
    return result.judge(DGPU_ROW, problems, facts)
