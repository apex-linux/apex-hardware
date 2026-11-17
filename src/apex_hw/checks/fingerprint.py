"""Fingerprint reader: present, claimed by libfprint, visible to fprintd.

Enrolling, unlocking and authorizing need a finger; see docs.
"""

from collections.abc import Callable
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


def _fprintd_list(host: host_lib.Host) -> host_lib.Command | None:
    """Lists the current user's fingers."""
    return host.run(["fprintd-list", host.env("USER") or "root"])


def enrolled(output: str) -> int:
    """Counts the fingers in `fprintd-list` output."""
    return len(re.findall(r"^ - #\d+:", output, re.MULTILINE))


def probe_enrolled(host: host_lib.Host) -> result.Result:
    """Checks that the current user has at least one finger enrolled."""
    done = _fprintd_list(host)
    count = enrolled(done.stdout) if done else 0
    if not count:
        return result.failed(ROW, "fprintd lists no enrolled finger")
    return result.passed(ROW, f"{count} fingers enrolled")


# /etc overrides the vendor's /usr/lib, as PAM itself reads them.
_PAM_DIRS = ("/etc/pam.d", "/usr/lib/pam.d")


def uses_fprintd(host: host_lib.Host, service: str, depth: int = 0) -> bool:
    """Returns whether a PAM service's auth stack reaches pam_fprintd.

    Follows "include" and "substack" lines (Fedora's authselect) and
    "@include" (Debian) a few levels deep.
    """
    text = next(
        (
            found
            for found in (host.read(f"{d}/{service}") for d in _PAM_DIRS)
            if found is not None
        ),
        "",
    )
    for line in text.splitlines():
        fields = line.split("#", 1)[0].split()
        if len(fields) > 1 and fields[0] == "@include":
            nested = fields[1]
        elif fields and fields[0] in ("auth", "-auth"):
            control, module = _control_and_module(fields[1:])
            if module.endswith("pam_fprintd.so"):
                return True
            nested = module if control in ("include", "substack") else ""
        else:
            nested = ""
        if nested and depth < 4 and uses_fprintd(host, nested, depth + 1):
            return True
    return False


def _control_and_module(fields: list[str]) -> tuple[str, str]:
    """Splits "[a=b c=d] pam_x.so args" or "sufficient pam_x.so args"."""
    if not fields:
        return "", ""
    if fields[0].startswith("["):
        for index, field in enumerate(fields):
            if field.endswith("]"):
                rest = fields[index + 1 :]
                return "[...]", rest[0] if rest else ""
        return "[...]", ""
    return fields[0], fields[1] if len(fields) > 1 else ""


def probe_pam(service: str) -> Callable[[host_lib.Host], result.Result]:
    """Returns a check that a PAM service accepts a finger.

    Args:
        service: "gdm-fingerprint" for the lock screen, "polkit-1" for
            authorizations.
    """

    def probe(host: host_lib.Host) -> result.Result:
        if uses_fprintd(host, service):
            return result.passed(ROW, f"PAM {service} uses pam_fprintd")
        return result.failed(
            ROW,
            f"PAM {service} does not use pam_fprintd (authselect"
            " with-fingerprint is off)",
        )

    return probe


def check(host: host_lib.Host) -> result.Result:
    """Checks that fprintd lists the reader for the current user."""
    known: set[str] = set()
    for path in host.glob(_HWDB):
        known |= known_readers(host.read(path) or "")
    readers = [d for d in devices.usb_devices(host) if d.ident in known]
    if not readers:
        return result.absent(ROW, "no reader that libfprint lists")
    reader = readers[0]
    done = _fprintd_list(host)
    output = done.stdout if done else ""
    name = re.search(r"Fingerprints for user \S+ on (.+?) \(", output)
    none = re.search(r"has no fingers enrolled for (.+?)\.", output)
    sensor = name or none
    problems: list[str] = []
    if done is None:
        problems.append("fprintd-list is not installed")
    elif sensor is None:
        problems.append("fprintd does not list the reader")
    fingers = enrolled(output)
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
