"""What a record says about the machine and the system it ran on."""

import shlex

from apex_hw.checks import devices
from apex_hw.platform import host as host_lib

_DMI = "/sys/class/dmi/id"


def os_release(text: str) -> dict[str, str]:
    """Parses os-release(5) text into its fields."""
    fields = {}
    for line in text.splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip() and not name.startswith("#"):
            parts = shlex.split(value, comments=False, posix=True)
            fields[name.strip()] = parts[0] if parts else ""
    return fields


def describe(host: host_lib.Host) -> dict[str, str]:
    """Returns the facts that identify this run's machine and system.

    Every value is a string; a fact the machine does not expose is
    "unknown".
    """
    release = os_release(
        host.read("/etc/os-release") or host.read("/usr/lib/os-release") or ""
    )

    def dmi(name: str) -> str:
        return host.read(f"{_DMI}/{name}") or "unknown"

    nvidia = host.read("/sys/module/nvidia/version")
    return {
        "machine": f"{dmi('sys_vendor')} {dmi('product_name')}",
        "bios": dmi("bios_version"),
        "os": release.get("PRETTY_NAME", "unknown"),
        "os_id": release.get("ID", "unknown"),
        "os_version": release.get("VERSION_ID", "unknown"),
        "image": release.get("IMAGE_VERSION", "unknown"),
        "variant": release.get("VARIANT_ID", "unknown"),
        "kernel": host.read("/proc/sys/kernel/osrelease") or "unknown",
        "nvidia": nvidia or "not loaded",
        "upower": devices.package_version(host, "upower") or "unknown",
        "libfprint": devices.package_version(host, "libfprint")
        or devices.package_version(host, "libfprint-2-2")
        or "unknown",
        "suspends": str(devices.suspend_count(host)),
    }
