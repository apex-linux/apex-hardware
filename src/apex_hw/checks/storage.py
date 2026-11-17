"""Storage: the system disk supports TRIM and something issues it."""

import os

from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

ROW = "storage"


def root_mount(mounts: str) -> tuple[str, str, str]:
    """Returns (source, fstype, options) of "/" from /proc/self/mounts."""
    found = ("", "", "")
    for line in mounts.splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[1] == "/":
            found = (fields[0], fields[2], fields[3])
    return found


def check(host: host_lib.Host) -> result.Result:
    """Checks NVMe disks for discard support and a TRIM schedule."""
    disks = host.glob("/sys/block/nvme*n*")
    if not disks:
        return result.absent(ROW, "no NVMe disk")
    disk = disks[0]
    name = os.path.basename(disk)
    model = host.read(f"{disk}/device/model") or "unknown model"
    discard = host.read(f"{disk}/queue/discard_max_bytes") or "0"
    timer = host.run(["systemctl", "is-enabled", "fstrim.timer"])
    timer_state = timer.stdout.strip() if timer else "unknown"
    _, fstype, options = root_mount(host.read("/proc/self/mounts") or "")
    online = "discard" in options.split(",") or "discard=async" in options
    problems: list[str] = []
    if discard == "0":
        problems.append(f"{name} does not support discard")
    if timer_state != "enabled" and not online:
        problems.append("neither fstrim.timer nor online discard")
    facts = [
        f"{name} {model}",
        f"discard_max_bytes {discard}",
        f"fstrim.timer {timer_state}",
        f"/ is {fstype or 'unknown'}{' with discard' if online else ''}",
    ]
    return result.judge(ROW, problems, facts)
