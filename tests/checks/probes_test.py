"""Tests the probes that judge a guided step after the person acted."""

import unittest

from apex_hw.checks import audio
from apex_hw.checks import cpu
from apex_hw.checks import fingerprint
from apex_hw.checks import gpu
from apex_hw.checks import network
from apex_hw.kernel import result
from apex_hw.platform.host import Command
from apex_hw.testkit.fake_host import FakeHost

PASS = result.Status.PASS
FAIL = result.Status.FAIL
NVIDIA = "/sys/bus/pci/devices/0000:01:00.0"


def _ok(stdout: str) -> Command:
    return Command(0, stdout)


class OffloadTest(unittest.TestCase):

    def _host(self, status: str) -> FakeHost:
        return FakeHost(
            files={
                f"{NVIDIA}/class": "0x030200",
                f"{NVIDIA}/vendor": "0x10de",
                f"{NVIDIA}/device": "0x25a2",
                f"{NVIDIA}/power/runtime_status": status,
            }
        )

    def test_passes_while_the_gpu_is_awake(self) -> None:
        self.assertIs(gpu.probe_offload(self._host("active")).status, PASS)

    def test_fails_when_the_gpu_slept_through(self) -> None:
        found = gpu.probe_offload(self._host("suspended"))
        self.assertIs(found.status, FAIL)
        self.assertIn("suspended", found.value)


class ResumedTest(unittest.TestCase):

    def _host(self, success: str, hw_sleep: str) -> FakeHost:
        return FakeHost(
            files={
                "/sys/power/suspend_stats/success": success,
                "/sys/power/suspend_stats/last_hw_sleep": hw_sleep,
            }
        )

    def test_passes_after_a_counted_suspend(self) -> None:
        found = cpu.probe_resumed(0)(self._host("1", "8000000"))
        self.assertIs(found.status, PASS, found.value)

    def test_fails_without_a_new_suspend(self) -> None:
        found = cpu.probe_resumed(1)(self._host("1", "8000000"))
        self.assertIs(found.status, FAIL)

    def test_fails_without_hardware_sleep(self) -> None:
        found = cpu.probe_resumed(0)(self._host("1", "0"))
        self.assertIn("hardware sleep", found.value)


class ProfileTest(unittest.TestCase):

    def _host(self, active: str, platform: str | None) -> FakeHost:
        files = {
            "/sys/devices/system/cpu/cpufreq/policy0/"
            "energy_performance_preference": "performance"
        }
        if platform is not None:
            files["/sys/firmware/acpi/platform_profile"] = platform
        return FakeHost(
            files=files,
            commands={tuple(cpu.PROFILE_COMMAND): _ok(f's "{active}"\n')},
        )

    def test_passes_when_firmware_follows(self) -> None:
        found = cpu.probe_profile("performance")(
            self._host("performance", "performance")
        )
        self.assertIs(found.status, PASS, found.value)

    def test_power_saver_accepts_quiet(self) -> None:
        found = cpu.probe_profile("power-saver")(
            self._host("power-saver", "quiet")
        )
        self.assertIs(found.status, PASS, found.value)

    def test_fails_when_firmware_lags(self) -> None:
        found = cpu.probe_profile("performance")(
            self._host("performance", "balanced")
        )
        self.assertIn("platform_profile is balanced", found.value)

    def test_fails_when_the_profile_did_not_change(self) -> None:
        found = cpu.probe_profile("performance")(self._host("balanced", None))
        self.assertIs(found.status, FAIL)


class PamTest(unittest.TestCase):

    def test_fedora_authselect_stack(self) -> None:
        host = FakeHost(
            files={
                "/usr/lib/pam.d/gdm-fingerprint": (
                    "auth  substack  fingerprint-auth\n"
                ),
                "/etc/pam.d/fingerprint-auth": (
                    "auth  sufficient  pam_fprintd.so\n"
                ),
                "/etc/pam.d/polkit-1": "auth include system-auth\n",
                "/etc/pam.d/system-auth": "auth required pam_unix.so\n",
            }
        )
        unlock = fingerprint.probe_pam("gdm-fingerprint")(host)
        authorize = fingerprint.probe_pam("polkit-1")(host)
        self.assertIs(unlock.status, PASS, unlock.value)
        self.assertIs(authorize.status, FAIL)
        self.assertIn("with-fingerprint", authorize.value)

    def test_debian_include_and_etc_override(self) -> None:
        host = FakeHost(
            files={
                "/usr/lib/pam.d/polkit-1": "@include common-auth\n",
                "/etc/pam.d/common-auth": (
                    "# auth sufficient pam_fprintd.so\n"
                    "auth [success=2 default=ignore] pam_fprintd.so"
                    " max-tries=1\n"
                ),
                "/etc/pam.d/gdm-fingerprint": "auth required pam_deny.so\n",
                "/usr/lib/pam.d/gdm-fingerprint": (
                    "auth required pam_fprintd.so\n"
                ),
            }
        )
        self.assertTrue(fingerprint.uses_fprintd(host, "polkit-1"))
        self.assertFalse(fingerprint.uses_fprintd(host, "gdm-fingerprint"))


class EnrolledTest(unittest.TestCase):

    def _host(self, listing: str) -> FakeHost:
        return FakeHost(
            commands={("fprintd-list", "owner"): _ok(listing)},
            environ={"USER": "owner"},
        )

    def test_passes_with_a_finger(self) -> None:
        host = self._host(
            "Fingerprints for user owner on X (press):\n - #0: a\n"
        )
        self.assertIs(fingerprint.probe_enrolled(host).status, PASS)

    def test_fails_without_fingers(self) -> None:
        host = self._host("User owner has no fingers enrolled for X.\n")
        self.assertIs(fingerprint.probe_enrolled(host).status, FAIL)


class HeadphonesTest(unittest.TestCase):

    def _host(self, available: str) -> FakeHost:
        return FakeHost(
            commands={
                ("pw-dump",): _ok(
                    '[{"type": "PipeWire:Interface:Device", "info": {"params":'
                    ' {"EnumRoute": [{"name": "analog-output-headphones",'
                    f' "available": "{available}"}}]}}}}}}]'
                )
            }
        )

    def test_passes_with_headphones_plugged_in(self) -> None:
        self.assertIs(audio.probe_headphones(self._host("yes")).status, PASS)

    def test_fails_with_an_empty_jack(self) -> None:
        self.assertIs(audio.probe_headphones(self._host("no")).status, FAIL)


class HdmiMonitorTest(unittest.TestCase):

    def _host(self, present: str) -> FakeHost:
        pci = "/sys/bus/pci/devices/0000:04:00.1"
        return FakeHost(
            files={
                "/sys/class/sound/hwC0D0/chip_name": "R6xx HDMI",
                f"{pci}/vendor": "0x1002",
                f"{pci}/device": "0x1637",
                f"{pci}/class": "0x040300",
                "/proc/asound/card0/pcm3p/info": "",
                "/proc/asound/card0/eld#0.0": f"monitor_present\t\t{present}\n",
            },
            links={
                "/sys/class/sound/card0/device": pci,
                f"{pci}/driver": "/sys/bus/pci/drivers/snd_hda_intel",
            },
        )

    def test_passes_with_a_monitor(self) -> None:
        found = audio.probe_hdmi_monitor(self._host("1"))
        self.assertIs(found.status, PASS, found.value)

    def test_fails_without_a_monitor(self) -> None:
        found = audio.probe_hdmi_monitor(self._host("0"))
        self.assertIs(found.status, FAIL)
        self.assertIn("no monitor with audio", found.value)

    def test_the_row_passes_without_a_monitor(self) -> None:
        self.assertIs(audio.check_hdmi(self._host("0")).status, PASS)


class BluetoothDevicesTest(unittest.TestCase):

    def _host(self, mouse_connected: str) -> FakeHost:
        return FakeHost(
            commands={
                ("bluetoothctl", "devices", "Paired"): _ok(
                    "Device AA:00 Headphones\nDevice BB:00 Mouse\n"
                ),
                ("bluetoothctl", "info", "AA:00"): _ok(
                    "\tIcon: audio-headset\n\tConnected: yes\n"
                ),
                ("bluetoothctl", "info", "BB:00"): _ok(
                    f"\tIcon: input-mouse\n\tConnected: {mouse_connected}\n"
                ),
            }
        )

    def test_passes_with_audio_and_input_connected(self) -> None:
        found = network.probe_bluetooth_devices(self._host("yes"))
        self.assertIs(found.status, PASS, found.value)

    def test_fails_when_the_mouse_is_not_connected(self) -> None:
        found = network.probe_bluetooth_devices(self._host("no"))
        self.assertIs(found.status, FAIL)
        self.assertIn("no connected input device", found.value)


if __name__ == "__main__":
    unittest.main()
