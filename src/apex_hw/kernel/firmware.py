"""Parses the firmware list that components/firmware installs."""

import dataclasses
import re

_DEVICE = re.compile(
    r"(pci|usb):[0-9a-f]{4}:[0-9a-f]{4}|cpu:(AuthenticAMD|GenuineIntel):[0-9]+"
)


class FirmwareListError(ValueError):
    """Raised when a line of the firmware list is malformed."""


@dataclasses.dataclass(frozen=True)
class FirmwareEntry:
    """One line of the list: a device and a glob under /usr/lib/firmware.

    Attributes:
        device: "pci:<vendor>:<device>", "usb:<vendor>:<product>" or
            "cpu:<vendor_id>:<family>".
        glob: A glob relative to /usr/lib/firmware.
        line: The line number, for error messages.
    """

    device: str
    glob: str
    line: int


def parse_firmware_list(text: str) -> list[FirmwareEntry]:
    """Parses the firmware list.

    Args:
        text: The content of firmware.txt.

    Returns:
        The entries in file order.

    Raises:
        FirmwareListError: A line is not "<device> <glob>", the device is
            malformed, or the glob is absolute or climbs out with "..".
    """
    entries = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 2:
            raise FirmwareListError(f"line {number}: want '<device> <glob>'")
        device, glob = fields
        if not _DEVICE.fullmatch(device):
            raise FirmwareListError(f"line {number}: bad device {device!r}")
        if glob.startswith("/") or ".." in glob.split("/"):
            raise FirmwareListError(f"line {number}: bad glob {glob!r}")
        entries.append(FirmwareEntry(device=device, glob=glob, line=number))
    return entries
