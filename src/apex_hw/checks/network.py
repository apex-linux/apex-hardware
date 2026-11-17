"""Wi-Fi and Bluetooth."""

from apex_hw.checks import devices
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

WIFI_ROW = "wifi"
BLUETOOTH_ROW = "bluetooth"


def nm_states(output: str) -> dict[str, str]:
    """Parses `nmcli -t -f DEVICE,STATE device` into {device: state}."""
    states = {}
    for line in output.splitlines():
        name, _, state = line.partition(":")
        states[name] = state
    return states


def check_wifi(host: host_lib.Host) -> result.Result:
    """Checks that a wireless interface has a driver and is connected."""
    interfaces = [
        path.rsplit("/", 2)[-2]
        for path in host.glob("/sys/class/net/*/wireless")
    ]
    if not interfaces:
        return result.absent(WIFI_ROW, "no wireless interface")
    name = interfaces[0]
    device = devices.owning_device(host, f"/sys/class/net/{name}")
    ident = device.ident if device else "unknown"
    bound = device.driver if device else ""
    done = host.run(["nmcli", "-t", "-f", "DEVICE,STATE", "device"])
    state = nm_states(done.stdout).get(name, "unknown") if done else "unknown"
    problems: list[str] = []
    if not bound:
        problems.append("no driver bound")
    if not state.startswith("connected"):
        problems.append(f"{name} is {state}")
    suspends = devices.suspend_count(host)
    facts = [
        f"{ident} {bound or 'no driver'} {name} {state}",
        f"{suspends} suspends this boot",
    ]
    return result.judge(WIFI_ROW, problems, facts)


def check_bluetooth(host: host_lib.Host) -> result.Result:
    """Checks that a Bluetooth controller is bound, unblocked and powered."""
    controllers = host.glob("/sys/class/bluetooth/hci[0-9]*")
    if not controllers:
        return result.absent(BLUETOOTH_ROW, "no Bluetooth controller")
    device = devices.owning_device(host, controllers[0])
    problems: list[str] = []
    if device is None or not device.driver:
        problems.append("no driver bound")
    # The controller's own switch; a platform switch beside it (such as
    # asus-bluetooth) can read blocked while the radio works.
    for rfkill in host.glob(f"{controllers[0]}/rfkill*"):
        if host.read(f"{rfkill}/hard") == "1":
            problems.append("hard-blocked")
        if host.read(f"{rfkill}/soft") == "1":
            problems.append("soft-blocked")
    show = host.run(["bluetoothctl", "show"])
    powered = show is not None and "Powered: yes" in show.stdout
    if not powered:
        problems.append("not powered")
    paired = host.run(["bluetoothctl", "devices", "Paired"])
    count = len(paired.stdout.splitlines()) if paired else 0
    ident = device.ident if device else "unknown"
    facts = [
        f"{ident} {device.driver if device else 'no driver'}",
        f"powered {'yes' if powered else 'no'}",
        f"{count} paired devices",
    ]
    return result.judge(BLUETOOTH_ROW, problems, facts)
