"""Tests each acceptance check against a fake machine.

The fixtures copy the shape of the reference machine's sysfs, with the
values the checks look at.
"""

import unittest

from apex_hw.checks import audio
from apex_hw.checks import battery
from apex_hw.checks import cpu
from apex_hw.checks import display
from apex_hw.checks import fingerprint
from apex_hw.checks import firmware
from apex_hw.checks import gpu
from apex_hw.checks import input as input_check
from apex_hw.checks import network
from apex_hw.checks import storage
from apex_hw.checks import webcam
from apex_hw.kernel import result
from apex_hw.platform.host import Command
from apex_hw.testkit.fake_host import FakeHost

PASS = result.Status.PASS
FAIL = result.Status.FAIL
ABSENT = result.Status.ABSENT

PCI = "/sys/bus/pci/devices"
NVIDIA = f"{PCI}/0000:01:00.0"
AMD = f"{PCI}/0000:04:00.0"


def _ok(stdout: str) -> Command:
    return Command(0, stdout)


def _gpus(nvidia_status: str = "suspended") -> FakeHost:
    return FakeHost(
        files={
            f"{AMD}/class": "0x030000",
            f"{AMD}/vendor": "0x1002",
            f"{AMD}/device": "0x1638",
            f"{AMD}/boot_vga": "1",
            f"{AMD}/drm/card2/card2-eDP-1/status": "connected",
            f"{AMD}/drm/card2/card2-HDMI-A-1/status": "disconnected",
            f"{NVIDIA}/class": "0x030200",
            f"{NVIDIA}/vendor": "0x10de",
            f"{NVIDIA}/device": "0x25a2",
            f"{NVIDIA}/power/control": "auto",
            f"{NVIDIA}/power/runtime_status": nvidia_status,
            f"{NVIDIA}/power_state": (
                "D3cold" if nvidia_status == "suspended" else "D0"
            ),
            f"{NVIDIA}/power/runtime_suspended_time": "900",
            f"{NVIDIA}/power/runtime_active_time": "100",
            "/proc/driver/nvidia/gpus/0000:01:00.0/power": (
                "Runtime D3 status:          Enabled (fine-grained)\n"
            ),
            "/sys/bus/pci/drivers/amdgpu/bind": "",
        },
        links={
            f"{AMD}/driver": "/sys/bus/pci/drivers/amdgpu",
            f"{NVIDIA}/driver": "/sys/bus/pci/drivers/nvidia",
        },
        environ={"XDG_SESSION_TYPE": "wayland"},
    )


class GpuTest(unittest.TestCase):

    def test_dgpu_passes_in_d3cold(self) -> None:
        found = gpu.check_dgpu(_gpus())
        self.assertIs(found.status, PASS, found.value)
        self.assertIn("90.0%", found.value)

    def test_dgpu_reports_the_nvidia_view(self) -> None:
        host = _gpus()
        host.files["/proc/driver/nvidia/params"] = (
            "DynamicPowerManagement: 3\nUseKernelSuspendNotifiers: 1\n"
            "EnableS0ixPowerManagement: 1\n"
        )
        host.files["/proc/driver/nvidia/gpus/0000:01:00.0/power"] = (
            "Runtime D3 status:          Enabled (fine-grained)\n"
        )
        found = gpu.check_dgpu(host)
        self.assertIs(found.status, PASS, found.value)
        self.assertIn("runtime D3 Enabled (fine-grained)", found.value)
        self.assertIn("UseKernelSuspendNotifiers 1", found.value)

    def test_dgpu_fails_when_nvidia_disables_runtime_d3(self) -> None:
        host = _gpus()
        host.files["/proc/driver/nvidia/gpus/0000:01:00.0/power"] = (
            "Runtime D3 status:          Disabled by default\n"
        )
        found = gpu.check_dgpu(host)
        self.assertIs(found.status, FAIL)
        self.assertIn("runtime D3 is Disabled by default", found.value)

    def test_dgpu_fails_when_awake_after_waiting(self) -> None:
        host = _gpus("active")
        found = gpu.check_dgpu(host)
        self.assertIs(found.status, FAIL)
        self.assertIn("runtime status is active", found.value)
        self.assertEqual(host.slept, 15)

    def test_dgpu_absent_without_second_gpu(self) -> None:
        host = _gpus()
        host.files = {k: v for k, v in host.files.items() if NVIDIA not in k}
        self.assertIs(gpu.check_dgpu(host).status, ABSENT)

    def test_igpu_passes(self) -> None:
        found = gpu.check_igpu(_gpus())
        self.assertIs(found.status, PASS, found.value)
        self.assertIn("eDP-1", found.value)

    def test_igpu_fails_on_x11(self) -> None:
        host = _gpus()
        host.environ["XDG_SESSION_TYPE"] = "x11"
        self.assertIs(gpu.check_igpu(host).status, FAIL)


class CpuTest(unittest.TestCase):

    def _host(self, fail: str = "0", hw_sleep: str = "123") -> FakeHost:
        policy = "/sys/devices/system/cpu/cpufreq/policy0"
        return FakeHost(
            files={
                f"{policy}/scaling_driver": "amd-pstate-epp",
                f"{policy}/scaling_governor": "powersave",
                f"{policy}/energy_performance_preference": "balance_power",
                "/sys/power/mem_sleep": "[s2idle]",
                "/sys/power/suspend_stats/success": "2",
                "/sys/power/suspend_stats/fail": fail,
                "/sys/power/suspend_stats/last_hw_sleep": hw_sleep,
            },
            commands={tuple(cpu.PROFILE_COMMAND): _ok('s "balanced"\n')},
        )

    def test_passes(self) -> None:
        found = cpu.check(self._host())
        self.assertIs(found.status, PASS, found.value)
        self.assertIn("profile balanced", found.value)

    def test_fails_on_failed_suspend(self) -> None:
        self.assertIs(cpu.check(self._host(fail="1")).status, FAIL)

    def test_fails_without_hardware_sleep(self) -> None:
        found = cpu.check(self._host(hw_sleep="0"))
        self.assertIn("never reached hardware sleep", found.value)


GDCTL = """\
Monitors:
└──Monitor eDP-1 (Built-in display)
   ├──Vendor: SDC
   ├──Product: 0x4154
   ├──Modes (2)
   │   ├──2880x1800@90.001
   │   │   └──Properties: (2)
   │   │       ├──is-current ⇒  yes
   │   │       └──is-preferred ⇒  yes
   │   └──2880x1800@60.001
   ├──Preferences
   │   └──Backlight:
   │       ├──active ⇒  True
   └──Properties: (7)
       ├──is-builtin ⇒  yes

Logical monitors:
└──Logical monitor #1
   ├──Scale: {scale}
   ├──Monitors: (1)
   │   └──eDP-1 (Built-in display)
"""


class DisplayTest(unittest.TestCase):

    def _host(self, scale: str) -> FakeHost:
        return FakeHost(
            files={"/sys/class/drm/card2-eDP-1/status": "connected"},
            commands={
                ("gdctl", "show", "--verbose"): _ok(GDCTL.format(scale=scale))
            },
        )

    def test_parses_gdctl(self) -> None:
        monitors = display.parse_gdctl(GDCTL.format(scale="2.0"))
        self.assertEqual(len(monitors), 1)
        monitor = monitors[0]
        self.assertEqual(monitor.current, "2880x1800@90.001")
        self.assertEqual(monitor.scale, 2.0)
        self.assertTrue(monitor.builtin and monitor.backlight)

    def test_passes_at_scale_2(self) -> None:
        found = display.check(self._host("2.0"))
        self.assertIs(found.status, PASS, found.value)

    def test_fails_at_another_scale(self) -> None:
        found = display.check(self._host("1.5"))
        self.assertIs(found.status, FAIL)
        self.assertIn("Apex default is 2.0", found.value)

    def test_best_mode_prefers_size_then_rate(self) -> None:
        modes = ["1920x1200@90.0", "2880x1800@60.0", "2880x1800@90.0"]
        self.assertEqual(display.best_mode(modes), "2880x1800@90.0")

    def test_absent_without_panel(self) -> None:
        self.assertIs(display.check(FakeHost()).status, ABSENT)


WIFI = f"{PCI}/0000:02:00.0"


class NetworkTest(unittest.TestCase):

    def _host(self, state: str) -> FakeHost:
        return FakeHost(
            files={
                "/sys/class/net/wlp2s0/wireless/x": "",
                f"{WIFI}/vendor": "0x8086",
                f"{WIFI}/device": "0x2723",
                f"{WIFI}/class": "0x028000",
            },
            links={
                "/sys/class/net/wlp2s0/device": WIFI,
                f"{WIFI}/driver": "/sys/bus/pci/drivers/iwlwifi",
            },
            commands={
                ("nmcli", "-t", "-f", "DEVICE,STATE", "device"): _ok(
                    f"wlp2s0:{state}\nlo:connected (externally)\n"
                )
            },
        )

    def test_wifi_passes_when_connected(self) -> None:
        found = network.check_wifi(self._host("connected"))
        self.assertIs(found.status, PASS, found.value)
        self.assertIn("8086:2723 iwlwifi", found.value)

    def test_wifi_fails_when_disconnected(self) -> None:
        found = network.check_wifi(self._host("disconnected"))
        self.assertIs(found.status, FAIL)

    def test_bluetooth_fails_when_blocked(self) -> None:
        usb = "/sys/bus/usb/devices/3-2"
        host = FakeHost(
            files={
                f"{usb}/idVendor": "8087",
                f"{usb}/idProduct": "0029",
                "/sys/class/bluetooth/hci0/rfkill0/soft": "1",
                "/sys/class/bluetooth/hci0/rfkill0/hard": "0",
            },
            links={
                "/sys/class/bluetooth/hci0/device": f"{usb}/3-2:1.0",
                f"{usb}/3-2:1.0/driver": "/sys/bus/usb/drivers/btusb",
            },
            commands={("bluetoothctl", "show"): _ok("Powered: yes\n")},
        )
        found = network.check_bluetooth(host)
        self.assertIs(found.status, FAIL)
        self.assertIn("soft-blocked", found.value)
        self.assertIn("8087:0029 btusb", found.value)


CODEC = "/sys/class/sound/hwC1D0"


class AudioTest(unittest.TestCase):

    def test_endpoints_from_pins(self) -> None:
        table = audio.pins(
            "0x12 0x90a60130\n0x14 0x90170110\n0x19 0x411111f0\n"
            "0x21 0x04211020\n"
        )
        self.assertEqual(
            audio.endpoints(table),
            {"internal mic", "internal speaker", "jack headphone"},
        )

    def test_driver_pins_override(self) -> None:
        table = audio.pins("0x19 0x411111f0", "0x19 0x03a11040")
        self.assertEqual(audio.endpoints(table), {"jack mic"})

    def test_fails_without_headphone_route(self) -> None:
        host = FakeHost(
            files={
                f"{CODEC}/chip_name": "ALC294",
                f"{CODEC}/init_pin_configs": "0x14 0x90170110\n"
                "0x21 0x04211020\n0x12 0x90a60130",
            },
            commands={
                ("pw-dump",): _ok(
                    '[{"type": "PipeWire:Interface:Device", "info": {"params":'
                    ' {"EnumRoute": [{"name": "analog-output-speaker"},'
                    ' {"name": "analog-input-mic"}]}}}]'
                )
            },
        )
        found = audio.check(host)
        self.assertIs(found.status, FAIL)
        self.assertIn("no analog-output-headphones", found.value)

    def test_hdmi_absent_without_codec(self) -> None:
        self.assertIs(audio.check_hdmi(FakeHost()).status, ABSENT)


class FingerprintTest(unittest.TestCase):

    def _host(self, listing: str) -> FakeHost:
        usb = "/sys/bus/usb/devices/3-1"
        return FakeHost(
            files={
                "/usr/lib/udev/hwdb.d/60-autosuspend-fingerprint-reader.hwdb": (
                    "usb:v04F3p0C6E*\n ID_AUTOSUSPEND=1\n"
                ),
                f"{usb}/idVendor": "04f3",
                f"{usb}/idProduct": "0c6e",
            },
            commands={("fprintd-list", "owner"): _ok(listing)},
            environ={"USER": "owner"},
        )

    def test_passes_with_enrolled_finger(self) -> None:
        found = fingerprint.check(
            self._host(
                "Fingerprints for user owner on ElanTech Fingerprint Sensor"
                " (press):\n - #0: right-index-finger\n"
            )
        )
        self.assertIs(found.status, PASS, found.value)
        self.assertIn("1 fingers enrolled", found.value)

    def test_passes_without_fingers(self) -> None:
        found = fingerprint.check(
            self._host(
                "User owner has no fingers enrolled for ElanTech Fingerprint"
                " Sensor.\n"
            )
        )
        self.assertIs(found.status, PASS, found.value)

    def test_fails_when_fprintd_lists_nothing(self) -> None:
        found = fingerprint.check(self._host("No devices available\n"))
        self.assertIs(found.status, FAIL)


class WebcamTest(unittest.TestCase):

    def test_fails_without_pipewire_source(self) -> None:
        usb = "/sys/bus/usb/devices/3-3"
        host = FakeHost(
            files={
                f"{usb}/idVendor": "13d3",
                f"{usb}/idProduct": "5458",
                f"{usb}/3-3:1.0/bInterfaceClass": "0e",
                "/sys/class/video4linux/video0/name": "USB2.0 HD UVC WebCam",
                "/dev/video0": "",
            },
            links={
                "/sys/class/video4linux/video0/device": f"{usb}/3-3:1.0",
                f"{usb}/3-3:1.0/driver": "/sys/bus/usb/drivers/uvcvideo",
            },
            commands={("pw-dump",): _ok("[]")},
        )
        found = webcam.check(host)
        self.assertIs(found.status, FAIL)
        self.assertIn("13d3:5458", found.value)
        self.assertIn("no PipeWire video source", found.value)


class StorageTest(unittest.TestCase):

    def test_passes_with_online_discard(self) -> None:
        host = FakeHost(
            files={
                "/sys/block/nvme0n1/device/model": "WD_BLACK SN770 1TB",
                "/sys/block/nvme0n1/queue/discard_max_bytes": "2199023255040",
                "/proc/self/mounts": "/dev/nvme0n1p3 / btrfs "
                "rw,ssd,discard=async 0 0\n",
            },
            commands={
                ("systemctl", "is-enabled", "fstrim.timer"): Command(
                    1, "disabled\n"
                )
            },
        )
        found = storage.check(host)
        self.assertIs(found.status, PASS, found.value)
        self.assertIn("btrfs with discard", found.value)


INPUT_DEVICES = """\
I: Bus=0011 Vendor=0001 Product=0001 Version=ab83
N: Name="AT Translated Set 2 keyboard"
P: Phys=isa0060/serio0/input0
B: EV=120013

I: Bus=0018 Vendor=04f3 Product=31de Version=0100
N: Name="ASUE1A00:00 04F3:31DE Touchpad"
P: Phys=i2c-ASUE1A00:00
B: KEY=e520 10000 0 0 0 0
B: ABS=2e0800000000003

I: Bus=0019 Vendor=0000 Product=0000 Version=0000
N: Name="Asus WMI hotkeys"
P: Phys=asus-nb-wmi/input0
"""


class InputTest(unittest.TestCase):

    def test_passes_on_reference_layout(self) -> None:
        host = FakeHost(
            files={
                "/proc/bus/input/devices": INPUT_DEVICES,
                "/sys/class/leds/asus::kbd_backlight/max_brightness": "3",
            }
        )
        found = input_check.check(host)
        self.assertIs(found.status, PASS, found.value)
        self.assertIn("three-finger", found.value)

    def test_fails_without_hotkeys(self) -> None:
        text = INPUT_DEVICES.split("\n\nI: Bus=0019", maxsplit=1)[0]
        host = FakeHost(files={"/proc/bus/input/devices": text})
        self.assertIn("no vendor hotkey", input_check.check(host).value)


class BatteryTest(unittest.TestCase):

    def _host(self, end: str, enabled: str) -> FakeHost:
        bat = "/sys/class/power_supply/BAT0"
        path = "/org/freedesktop/UPower/devices/battery_BAT0"

        def prop(name: str) -> tuple[str, ...]:
            return (
                "busctl",
                "get-property",
                "org.freedesktop.UPower",
                path,
                "org.freedesktop.UPower.Device",
                name,
            )

        return FakeHost(
            files={
                f"{bat}/type": "Battery",
                f"{bat}/charge_control_end_threshold": end,
            },
            commands={
                prop("ChargeThresholdSupported"): _ok("b true\n"),
                prop("ChargeThresholdEnabled"): _ok(f"b {enabled}\n"),
                prop("ChargeEndThreshold"): _ok("u 80\n"),
            },
        )

    def test_passes_at_80(self) -> None:
        found = battery.check(self._host("80", "true"))
        self.assertIs(found.status, PASS, found.value)

    def test_fails_when_disabled(self) -> None:
        found = battery.check(self._host("100", "false"))
        self.assertIs(found.status, FAIL)
        self.assertIn("off in UPower", found.value)

    def test_absent_without_threshold(self) -> None:
        host = FakeHost(files={"/sys/class/power_supply/BAT0/type": "Battery"})
        self.assertIs(battery.check(host).status, ABSENT)


class FirmwareTest(unittest.TestCase):

    def _host(self, files: dict[str, str]) -> FakeHost:
        return FakeHost(
            files={
                "/sys/firmware/efi/systab": "",
                f"{WIFI}/vendor": "0x8086",
                f"{WIFI}/device": "0x2723",
                f"{WIFI}/class": "0x028000",
                "/proc/cpuinfo": (
                    "vendor_id\t: AuthenticAMD\ncpu family\t: 25\n"
                ),
                "/list": "pci:8086:2723 iwlwifi-cc-a0-*.ucode*\n"
                "pci:1002:1638 amdgpu/green_sardine_*\n"
                "cpu:AuthenticAMD:25 amd-ucode/microcode_amd_fam19h.bin*\n",
                **files,
            }
        )

    def test_checks_only_present_devices(self) -> None:
        found = firmware.check(
            self._host(
                {
                    "/usr/lib/firmware/iwlwifi-cc-a0-77.ucode.xz": "",
                    "/usr/lib/firmware/amd-ucode/microcode_amd_fam19h.bin.xz": (
                        ""
                    ),
                }
            ),
            list_path="/list",
        )
        self.assertIs(found.status, PASS, found.value)
        self.assertIn("2 of 2 firmware files", found.value)

    def test_fails_on_missing_file(self) -> None:
        found = firmware.check(self._host({}), list_path="/list")
        self.assertIs(found.status, FAIL)
        self.assertIn("missing iwlwifi-cc-a0-*.ucode*", found.value)


if __name__ == "__main__":
    unittest.main()
