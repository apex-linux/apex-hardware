"""Fingerprint reader: present, claimed by libfprint, visible to fprintd.

Enrolling, unlocking and authorizing need a finger; see docs.
"""

import re

from apex_hw.checks import devices
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

ROW = "fingerprint"
# libfprint installs the IDs of every reader it knows into this hwdb.
_HWDB = "/usr/lib/udev/hwdb.d/*fingerprint*.hwdb"


def known_readers(hwdb: str) -> set[str]:
    """Returns "vendor:product" IDs from libfprint's hwdb text."""
    return {
        f"{vendor}:{product}".lower()
        for vendor, product in re.findall(
            r"^usb:v([0-9A-Fa-f]{4})p([0-9A-Fa-f]{4})\*", hwdb, re.MULTILINE
        )
    }


def check(host: host_lib.Host) -> result.Result:
    """Checks that fprintd lists the reader for the current user."""
    known: set[str] = set()
    for path in host.glob(_HWDB):
        known |= known_readers(host.read(path) or "")
    readers = [d for d in devices.usb_devices(host) if d.ident in known]
    if not readers:
        return result.absent(ROW, "no reader that libfprint lists")
    reader = readers[0]
    user = host.env("USER") or "root"
    done = host.run(["fprintd-list", user])
    output = done.stdout if done else ""
    name = re.search(r"Fingerprints for user \S+ on (.+?) \(", output)
    none = re.search(r"has no fingers enrolled for (.+?)\.", output)
    sensor = name or none
    problems: list[str] = []
    if done is None:
        problems.append("fprintd-list is not installed")
    elif sensor is None:
        problems.append("fprintd does not list the reader")
    fingers = len(re.findall(r"^ - #\d+:", output, re.MULTILINE))
    version = devices.package_version(
        host, "libfprint"
    ) or devices.package_version(host, "libfprint-2-2")
    facts = [
        f"{reader.ident}",
        f"fprintd sees {sensor.group(1) if sensor else 'nothing'}",
        f"{fingers} fingers enrolled",
        f"libfprint {version or 'unknown'}",
    ]
    return result.judge(ROW, problems, facts)
