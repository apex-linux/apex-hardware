"""The checks in the order they run, one per reference machine row."""

from collections.abc import Callable
import functools

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
from apex_hw.platform import host as host_lib

Check = Callable[[host_lib.Host], result.Result]


def all_checks(firmware_list: str) -> list[tuple[str, Check]]:
    """Returns (row, check) pairs in table order.

    The discrete GPU runs first: other checks start programs that could
    wake it, and its reading must come from an idle machine.

    Args:
        firmware_list: Path of firmware.txt.
    """
    return [
        (gpu.DGPU_ROW, gpu.check_dgpu),
        (cpu.ROW, cpu.check),
        (gpu.IGPU_ROW, gpu.check_igpu),
        (display.ROW, display.check),
        (network.WIFI_ROW, network.check_wifi),
        (network.BLUETOOTH_ROW, network.check_bluetooth),
        (audio.ROW, audio.check),
        (audio.HDMI_ROW, audio.check_hdmi),
        (fingerprint.ROW, fingerprint.check),
        (webcam.ROW, webcam.check),
        (storage.ROW, storage.check),
        (input_check.ROW, input_check.check),
        (battery.ROW, battery.check),
        (
            firmware.ROW,
            functools.partial(firmware.check, list_path=firmware_list),
        ),
    ]
