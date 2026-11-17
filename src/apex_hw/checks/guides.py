"""What a person does for each row that a program cannot judge alone.

A row passes only when its automated check passes and every guided step
here passed too. A step either runs a probe after the person acted, asks
them one yes-or-no question, or both; nothing is green from detection
alone.
"""

from collections.abc import Callable
import dataclasses

from apex_hw.checks import audio
from apex_hw.checks import battery
from apex_hw.checks import cpu
from apex_hw.checks import display
from apex_hw.checks import fingerprint
from apex_hw.checks import gpu
from apex_hw.checks import input as input_check
from apex_hw.checks import network
from apex_hw.checks import webcam
from apex_hw.kernel import result
from apex_hw.platform import host as host_lib

Probe = Callable[[host_lib.Host], result.Result]

# The apps the steps open, by the name GNOME shows, and the Fedora RPM
# that ships each one. All are RPMs in the image; requires.txt lists them.
APPS = {
    "Settings": "gnome-control-center",
    "Text Editor": "gnome-text-editor",
    "Camera": "snapshot",
    "Firefox": "firefox",
}

# A browser page from Mozilla that shows the camera after a permission
# prompt; it exercises the same camera portal as a video call.
CAMERA_TEST_PAGE = "https://mozilla.github.io/webrtc-landing/gum_test.html"


@dataclasses.dataclass(frozen=True)
class Step:
    """One thing the person does, and how the result is judged.

    Attributes:
        name: A few words for the report, such as "speakers".
        do: What to do, shown before anything is asked.
        ask: A yes-or-no question about what happened, or None.
        probe: A check run once the person says they are done, or None.
            A failing probe ends the step without asking.
    """

    name: str
    do: str
    ask: str | None = None
    probe: Probe | None = None


# Rows whose automated check must also pass after a suspend and resume.
RESUME_ROWS = (gpu.DGPU_ROW, cpu.ROW, network.WIFI_ROW, battery.ROW)

SUSPEND_NAME = "suspend and resume"
SUSPEND_DO = (
    "Suspend the machine: open the system menu at the top right, press the"
    " power button and choose Suspend. Wait ten seconds, wake it with the"
    " power key, log in, and wait until Wi-Fi is connected again."
)

GUIDES: dict[str, tuple[Step, ...]] = {
    gpu.DGPU_ROW: (
        Step(
            name="app on the discrete GPU",
            do=(
                "Right-click Text Editor in the app grid and choose"
                ' "Launch using Discrete Graphics Card". Keep it open.'
            ),
            ask="Did the app open and draw its window normally?",
            probe=gpu.probe_offload,
        ),
        Step(
            name="powers down after the app",
            do="Close that app.",
            probe=gpu.check_dgpu,
        ),
    ),
    cpu.ROW: tuple(
        Step(
            name=f"{label} mode",
            do=f"Open Quick Settings (top right) and choose {label} mode.",
            probe=cpu.probe_profile(profile),
        )
        for profile, label in (
            ("performance", "Performance"),
            ("power-saver", "Power Saver"),
            ("balanced", "Balanced"),
        )
    ),
    display.ROW: (
        Step(
            name="brightness",
            do=(
                "Move the brightness slider in Quick Settings all the way"
                " down and back up."
            ),
            ask="Did the panel get darker and then brighter?",
        ),
    ),
    network.BLUETOOTH_ROW: (
        Step(
            name="headphones and a mouse",
            do=(
                "In Settings, Bluetooth, pair and connect Bluetooth"
                " headphones and a Bluetooth mouse or keyboard."
            ),
            ask=(
                "Does sound play in the headphones, and does the mouse or"
                " keyboard work?"
            ),
            probe=network.probe_bluetooth_devices,
        ),
    ),
    audio.ROW: (
        Step(
            name="speakers",
            do=(
                "Unplug any headphones. In Settings, Sound, choose the"
                " built-in speakers as output, press Test and play the left"
                " and the right channel."
            ),
            ask="Did each sound come from the correct side, without crackle?",
        ),
        Step(
            name="headphone jack",
            do="Plug wired headphones into the jack. Test again in Sound.",
            ask="Did the sound play in the headphones and not the speakers?",
            probe=audio.probe_headphones,
        ),
        Step(
            name="internal microphone",
            do=(
                "Unplug the headphones. In Settings, Sound, Input, choose"
                " the internal microphone and speak normally."
            ),
            ask="Does the input level move while you speak?",
        ),
    ),
    audio.HDMI_ROW: (
        Step(
            name="HDMI display",
            do="Connect a display with speakers, such as a TV, over HDMI.",
            ask="Does the HDMI display show the desktop?",
            probe=audio.probe_hdmi_monitor,
        ),
        Step(
            name="HDMI sound",
            do="In Settings, Sound, choose the HDMI output and press Test.",
            ask="Did the sound play on the HDMI display?",
        ),
    ),
    fingerprint.ROW: (
        Step(
            name="enroll",
            do=(
                "In Settings, System, Users, open Fingerprint Login and"
                " enroll a finger. Delete it and enroll again, three"
                " enrollments in all."
            ),
            ask="Did all three enrollments finish without an error?",
            probe=fingerprint.probe_enrolled,
        ),
        Step(
            name="unlock",
            do="Lock the screen with Super+L, then unlock it with your finger.",
            ask="Did your finger unlock the screen?",
            probe=fingerprint.probe_pam("gdm-fingerprint"),
        ),
        Step(
            name="authorize",
            do=(
                "In a terminal, run `pkexec true` and touch the reader when"
                " it asks."
            ),
            ask="Did your finger authorize it without the password?",
            probe=fingerprint.probe_pam("polkit-1"),
        ),
    ),
    webcam.ROW: (
        Step(
            name="camera app",
            do="Open Camera.",
            ask="Do you see a live, sharp picture?",
        ),
        Step(
            name="browser",
            do=(
                f"Close Camera. In Firefox, open {CAMERA_TEST_PAGE},"
                " press the video button and allow the camera."
            ),
            ask="Do you see a live picture in the page?",
        ),
    ),
    input_check.ROW: (
        Step(
            name="gestures",
            do=(
                "On the touchpad, swipe up with three fingers, then swipe"
                " left and right with three fingers."
            ),
            ask="Did the overview open and the workspaces switch?",
        ),
        Step(
            name="keyboard backlight",
            do="Press the keyboard backlight key until it has gone round.",
            ask="Did the keyboard light step through its levels and off?",
        ),
        Step(
            name="function keys",
            do=(
                "Press each function key: volume, mute, microphone mute,"
                " brightness, and Fn+F5 for the power mode."
            ),
            ask="Did every key show its on-screen display or do its job?",
        ),
    ),
}
