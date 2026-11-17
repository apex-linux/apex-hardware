"""Finds devices through sysfs attributes the kernel caches."""

import dataclasses
import os
import posixpath

from apex_hw.platform import host as host_lib

PCI = "/sys/bus/pci/devices"
USB = "/sys/bus/usb/devices"


@dataclasses.dataclass(frozen=True)
class Device:
    """A PCI or USB device.

    Attributes:
        path: Its sysfs directory.
        vendor: The vendor ID in lowercase hex, without "0x".
        product: The device or product ID in lowercase hex, without "0x".
        driver: The bound driver's name, or "" when none is bound.
    """

    path: str
    vendor: str
    product: str
    driver: str

    @property
    def ident(self) -> str:
        """Returns "vendor:product"."""
        return f"{self.vendor}:{self.product}"


def _hex(value: str | None) -> str:
    """Returns a sysfs ID without "0x", lowercase, or "" if missing."""
    return (value or "").lower().removeprefix("0x")


def driver(host: host_lib.Host, path: str) -> str:
    """Returns the name of the driver bound to a sysfs device, or ""."""
    target = host.readlink(f"{path}/driver")
    return os.path.basename(target) if target else ""


def pci_devices(host: host_lib.Host, class_prefix: str = "") -> list[Device]:
    """Lists PCI devices, optionally those whose class starts with a prefix.

    Args:
        host: The machine.
        class_prefix: Hex digits of the class code without "0x", such as
            "03" for display controllers.

    Returns:
        The devices in bus order.
    """
    devices = []
    for path in host.glob(f"{PCI}/*"):
        if not _hex(host.read(f"{path}/class")).startswith(class_prefix):
            continue
        devices.append(
            Device(
                path=path,
                vendor=_hex(host.read(f"{path}/vendor")),
                product=_hex(host.read(f"{path}/device")),
                driver=driver(host, path),
            )
        )
    return devices


def usb_devices(host: host_lib.Host) -> list[Device]:
    """Lists USB devices with the driver of their first bound interface."""
    devices = []
    for path in host.glob(f"{USB}/*"):
        vendor = host.read(f"{path}/idVendor")
        if vendor is None:
            continue
        drivers = [driver(host, iface) for iface in host.glob(f"{path}/*:*")]
        devices.append(
            Device(
                path=path,
                vendor=_hex(vendor),
                product=_hex(host.read(f"{path}/idProduct")),
                driver=next((name for name in drivers if name), ""),
            )
        )
    return devices


def owning_device(host: host_lib.Host, path: str) -> Device | None:
    """Returns the PCI or USB device that a class device belongs to.

    Args:
        host: The machine.
        path: A class device such as /sys/class/net/wlan0; its "device"
            link points at a PCI function, a USB interface or a USB device.

    Returns:
        The device, or None when it is neither PCI nor USB.
    """
    if host.readlink(f"{path}/device") is None:
        return None
    bound = driver(host, f"{path}/device")
    target = host.realpath(f"{path}/device")
    for _ in range(3):
        usb_vendor = host.read(f"{target}/idVendor")
        if usb_vendor is not None:
            product = host.read(f"{target}/idProduct")
            return Device(target, _hex(usb_vendor), _hex(product), bound)
        pci_vendor = host.read(f"{target}/vendor")
        if pci_vendor is not None and host.read(f"{target}/class"):
            product = host.read(f"{target}/device")
            return Device(target, _hex(pci_vendor), _hex(product), bound)
        target = posixpath.dirname(target)
    return None


def kernel_log(host: host_lib.Host, pattern: str) -> list[str] | None:
    """Returns this boot's kernel log lines matching a regex, or None.

    None means the journal could not be read, for example because the
    user is not in a group that may read it.
    """
    done = host.run(
        ["journalctl", "-k", "-b", "-q", "-o", "cat", "--grep", pattern]
    )
    if done is None or done.returncode not in (0, 1):
        return None
    return done.stdout.splitlines()


def package_version(host: host_lib.Host, name: str) -> str | None:
    """Returns an installed package's version from rpm or dpkg, or None."""
    for argv in (
        ["rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}", name],
        ["dpkg-query", "-W", "-f", "${Version}", name],
    ):
        done = host.run(argv)
        if done is not None and done.returncode == 0 and done.stdout:
            return done.stdout.strip()
    return None


def suspend_count(host: host_lib.Host) -> int:
    """Returns the number of successful system suspends since boot."""
    try:
        return int(host.read("/sys/power/suspend_stats/success") or "0")
    except ValueError:
        return 0
