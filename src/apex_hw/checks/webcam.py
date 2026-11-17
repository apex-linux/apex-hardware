"""Webcam: a USB video class camera that the user and PipeWire can open."""

import os

from apex_hw.checks import devices
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

ROW = "webcam"


def check(host: host_lib.Host) -> result.Result:
    """Checks the driver, device node access and the PipeWire source."""
    cameras = []
    for path in host.glob("/sys/class/video4linux/video*"):
        if host.read(f"{path}/device/bInterfaceClass") == "0e":
            cameras.append(path)
    if not cameras:
        return result.absent(ROW, "no USB video class camera")
    camera = cameras[0]
    device = devices.owning_device(host, camera)
    node = f"/dev/{os.path.basename(camera)}"
    problems: list[str] = []
    if device is None or device.driver != "uvcvideo":
        problems.append("uvcvideo is not bound")
    if not host.access(node, os.R_OK | os.W_OK):
        problems.append(f"this user cannot open {node}")
    dump = host.run(["pw-dump"])
    if dump is None or dump.returncode != 0:
        source = "PipeWire not reachable"
    elif '"Video/Source"' in dump.stdout:
        source = "PipeWire video source present"
    else:
        source = "no PipeWire video source"
        problems.append(source)
    ident = device.ident if device else "unknown"
    facts = [
        f"{ident} {host.read(f'{camera}/name')}",
        node,
        source,
    ]
    return result.judge(ROW, problems, facts)
