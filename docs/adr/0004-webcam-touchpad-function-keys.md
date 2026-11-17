# ADR 0004: Webcam, touchpad and function keys need no rules

*   Status: proposed
*   Date: 2026-11-17
*   Decides for: this repository

## Context

The previous attempt never covered the webcam, the touchpad or the function
keys. The specification wants video in the camera app and the browser,
touchpad gestures, the keyboard backlight and the hotkeys to work.

What the running host shows (Ubuntu 26.04, kernel 7.0.0-43, 2026-11-17):

*   **Webcam:** IMC Networks `13d3:5458`, a plain USB video class camera
    bound to `uvcvideo`, with `/dev/video0` (capture) and `/dev/video1`
    (metadata), and a third interface of class `0xfe` (firmware update),
    which no driver needs. There is no infrared camera. PipeWire's V4L2
    monitor publishes it as a video source.
*   **Touchpad:** ELAN `04f3:31de` on I2C (ACPI `ASUE1A00`), bound to
    `hid-multitouch`. It reports up to five fingers, enough for GNOME's
    three- and four-finger gestures.
*   **Keyboard and function keys:** an AT keyboard on `serio0`, the
    `asus-nb-wmi` "Asus WMI hotkeys" device, the `asus::kbd_backlight` LED
    with three levels, and `platform_profile` through
    `throttle_thermal_policy`, which Fn+F5 cycles. The kernel log has no
    "unknown key" line.

Upstream, as of 2026-11-17: no uvcvideo quirk, libinput quirk, systemd
keyboard hwdb entry or HID quirk exists or is reported as needed for these
devices. `asus-wmi` handles the backlight keys itself. Fedora 45 builds
Firefox with `media.webrtc.camera.allow-pipewire` on, so the browser uses
the camera portal, and Snapshot 51 works with a UVC camera through
PipeWire. tuned-ppd 2.28 in Fedora 45 follows `platform_profile` changes
(`sysfs_acpi_monitor`), so Fn+F5 and Quick Settings stay in step.

The M7400QC also has an ASUS DialPad in the touchpad. No upstream driver
supports it; only the out-of-tree `asus-dialpad-driver` does.

## Decision

*   Ship no rules for the webcam, the touchpad or the function keys. The
    `webcam` and `input` acceptance rows check them, and their manual parts
    (a browser call and Snapshot; gestures; every function key) decide
    whether the rows are done.
*   The DialPad is out of scope: it is not in the specification's table,
    and supporting it means shipping an out-of-tree userspace driver.
*   If a function key turns out to be dead, the fix is a `60-keyboard.hwdb`
    entry keyed by DMI, sent to systemd, and carried here until it lands.

## Consequences

*   Nothing to maintain. A regression in Fedora's kernel, libinput or
    PipeWire shows up as a failing acceptance row.
*   The DialPad stays an inert part of the touchpad surface.

## Sources

*   libinput quirks: <https://gitlab.freedesktop.org/libinput/libinput/-/tree/main/quirks>
*   systemd keyboard hwdb:
    <https://raw.githubusercontent.com/systemd/systemd/main/hwdb.d/60-keyboard.hwdb>
*   Fedora 45 Firefox: <https://src.fedoraproject.org/rpms/firefox/raw/f45/f/firefox.spec>
*   Snapshot: <https://gitlab.gnome.org/GNOME/snapshot/-/raw/main/README.md>
*   DialPad driver: <https://github.com/asus-linux-drivers/asus-dialpad-driver>
*   The host measurements: [the Ubuntu baseline](../baselines/2026-11-17-ubuntu-26.04.md)
