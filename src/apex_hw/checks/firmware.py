"""Firmware: booted with UEFI, and every present device's firmware exists."""

import os

from apex_hw.checks import devices
from apex_hw.kernel import firmware as firmware_list
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

ROW = "firmware"
INSTALLED_LIST = "/usr/share/apex-hardware/firmware.txt"
_FIRMWARE = "/usr/lib/firmware"
_SECURE_BOOT = (
    "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
)


def cpu_key(cpuinfo: str) -> str:
    """Returns "cpu:<vendor_id>:<family>" for the first CPU."""
    fields: dict[str, str] = {}
    for line in cpuinfo.splitlines():
        key, _, value = line.partition(":")
        fields.setdefault(key.strip(), value.strip())
    return f"cpu:{fields.get('vendor_id', '')}:{fields.get('cpu family', '')}"


def present_keys(host: host_lib.Host) -> set[str]:
    """Returns the firmware list keys of the devices on this machine."""
    keys = {f"pci:{d.ident}" for d in devices.pci_devices(host)}
    keys |= {f"usb:{d.ident}" for d in devices.usb_devices(host)}
    keys.add(cpu_key(host.read("/proc/cpuinfo") or ""))
    return keys


def check(
    host: host_lib.Host, list_path: str = INSTALLED_LIST
) -> result.Result:
    """Checks UEFI boot, Secure Boot state and firmware files."""
    problems: list[str] = []
    if not host.glob("/sys/firmware/efi"):
        problems.append("not booted with UEFI")
    secure = host.read_bytes(_SECURE_BOOT)
    secure_boot = "on" if secure and secure[-1] == 1 else "off"
    text = host.read(list_path)
    if text is None:
        return result.failed(ROW, f"cannot read {list_path}")
    present = present_keys(host)
    wanted = [
        entry
        for entry in firmware_list.parse_firmware_list(text)
        if entry.device in present
    ]
    missing = [
        entry.glob
        for entry in wanted
        if not host.glob(os.path.join(_FIRMWARE, entry.glob))
    ]
    problems.extend(f"missing {glob}" for glob in missing)
    failures = devices.kernel_log(host, "Direct firmware load for .* failed")
    if failures:
        problems.append(f"{len(failures)} failed firmware loads in the log")
    facts = [
        f"UEFI, Secure Boot {secure_boot}",
        f"{len(wanted) - len(missing)} of {len(wanted)} firmware files",
        "kernel log "
        + ("unreadable" if failures is None else f"{len(failures)} failures"),
    ]
    return result.judge(ROW, problems, facts)
