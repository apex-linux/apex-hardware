# Acceptance checks

One check per row of the
[reference machine table](https://github.com/apex-linux/apex/blob/main/docs/spec.md#reference-machine).
A row is done when its check passes on the machine, not when a fix is
written.

## Running them

From a clone, logged in to GNOME as an ordinary user:

```bash
just accept
just accept dgpu battery
just accept --json
```

On an installed Apex without a clone, run the copy in the image:

```bash
/usr/libexec/apex-hardware/accept
```

Each row prints `PASS`, `FAIL`, or `SKIP` when the machine does not have
that hardware, followed by what was measured. The exit status is 1 when any
row fails. The checks only read: they never need root, never write to the
system, and never read PCI configuration space, so they do not wake a
suspended GPU. The `dgpu` row runs first for that reason; leave the machine
idle for a minute before a run.

## What each row checks

The automated part is what a program can see. The manual part needs a
person, a finger or a cable; do it once per acceptance run and record it
next to the output.

| Row | Matches | Automated | Manual |
| --- | --- | --- | --- |
| `cpu` | Always | cpufreq driver, governor and EPP; a power profile on D-Bus; s2idle or deep offered; no failed suspend this boot; the last s2idle reached hardware sleep | Switch the three profiles in Quick Settings; suspend, wake, run again |
| `igpu` | The `boot_vga` GPU | Driver bound; a connected display; the session is Wayland | None |
| `dgpu` | Any other display controller | `power/control` is `auto`; runtime-suspended within 15 s; `D3cold`; suspended share since boot; with `nvidia` bound, the driver's runtime D3 status is `Enabled` and its power parameters | Launch an app with "Launch using Discrete Graphics Card", then run `dgpu` again |
| `display` | A connected eDP, LVDS or DSI connector | The panel runs its largest mode at its highest refresh rate; backlight control; scale 2 on the reference panel (SDC `0x4154`) | Move the brightness slider |
| `wifi` | A wireless interface | Driver bound; NetworkManager connected | Suspend, wake, run again |
| `bluetooth` | An HCI controller | Driver bound; its rfkill not blocked; powered; paired device count | Pair headphones and a mouse; play audio through them |
| `audio` | An analog HD audio codec | Pins wire an internal speaker, a headphone jack and an internal mic; PipeWire offers speaker and headphone routes and an analog input | Speakers left and right, the headphone jack, a recording from the internal mic, after a cold boot and after a suspend |
| `hdmi_audio` | An HDMI or DisplayPort codec | Controller driver bound; playback devices; connected monitors with audio | Play audio on an HDMI display |
| `fingerprint` | A USB reader that libfprint lists | fprintd lists it for this user; enrolled finger count; libfprint version | Enroll a finger in Settings, three times in a row |
| `webcam` | A USB video class camera | `uvcvideo` bound; this user can open the node; PipeWire has a video source | Video in Snapshot and in a browser call |
| `storage` | An NVMe disk | The disk supports discard; `fstrim.timer` is enabled or `/` is mounted with discard | None |
| `input` | An internal keyboard or touchpad | Internal keyboard; a touchpad with three-finger reports; a vendor hotkey device; keyboard backlight | Three- and four-finger gestures, each function key, backlight keys |
| `battery` | A battery with `charge_control_end_threshold` | UPower supports and enables the limit; sysfs equals UPower's end threshold; the threshold is below 100 | Reboot and run again; suspend, wake and run again |
| `firmware` | Always | Booted with UEFI; Secure Boot state; every firmware file the present devices need; no failed firmware load in this boot's kernel log | None |

A check that cannot read the journal (the user is not in the `wheel` or
`systemd-journal` group) says so instead of failing.

## Baselines

Results recorded on the reference machine are in [baselines/](baselines/).
