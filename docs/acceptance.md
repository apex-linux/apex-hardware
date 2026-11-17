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
apex-accept
```

`apex-accept --list` lists the rows. A run of every row writes a dated
record to `~/apex-acceptance/` (`--record-dir` to change it, `--no-record`
to skip it); see [records/](records/).

Each row prints `PASS`, `FAIL`, `TODO` when part of it still needs a
person, or `SKIP` when the machine does not have that hardware, followed by
what was measured. A row passes only when its automated check and every
guided step for it passed; detection alone leaves it at `TODO`.

At a terminal the run guides you: after the automated checks it asks you
to suspend and wake the machine, unless it already resumed once in this
boot, and measures the resume rows again; then it walks through each row's
steps, telling you what to do and asking one yes-or-no question. Answer `s`
to skip a step; its row stays `TODO`. `--no-guide`, or a run without a
terminal, asks nothing.

The exit status is 1 when any row fails, 3 when none fails but some need a
person, and 0 when every row passed or is absent. The checks only read:
they never need root, never write to the system, and never read PCI
configuration space, so they do not wake a suspended GPU. The `dgpu` row
runs first for that reason; leave the machine idle for a minute before a
run.

## What each row checks

The automated part is what a program can see. The guided part needs a
person, a finger or a cable; the run asks for it, and the steps are in
[guides.py](../src/apex_hw/checks/guides.py). Rows marked "after resume"
also run their automated check again on a resumed machine.

| Row | Matches | Automated | Guided |
| --- | --- | --- | --- |
| `cpu` | Always | cpufreq driver, governor and EPP; a power profile on D-Bus; s2idle or deep offered; no failed suspend this boot; the last s2idle reached hardware sleep | After resume; switch the three power modes |
| `igpu` | The `boot_vga` GPU | Driver bound; a connected display; the session is Wayland | None |
| `dgpu` | Any other display controller | `power/control` is `auto`; runtime-suspended within 15 s; `D3cold`; suspended share since boot; with `nvidia` bound, the driver's runtime D3 status is `Enabled` and its power parameters | After resume; an app launched on the discrete GPU wakes it (probe) and draws; it powers down again once closed (probe) |
| `display` | A connected eDP, LVDS or DSI connector | The panel runs its largest mode at its highest refresh rate; backlight control; scale 2 on the reference panel (SDC `0x4154`) | The brightness slider dims and brightens the panel |
| `wifi` | A wireless interface | Driver bound; NetworkManager connected | After resume, connected again within 30 s |
| `bluetooth` | An HCI controller | Driver bound; its rfkill not blocked; powered; paired device count | Headphones and a mouse or keyboard connected (probe); sound and input work |
| `audio` | An analog HD audio codec | Pins wire an internal speaker, a headphone jack and an internal mic; PipeWire offers speaker and headphone routes and an analog input | Speakers left and right; headphones detected in the jack (probe) and playing; the internal mic's input level moves |
| `hdmi_audio` | An HDMI or DisplayPort codec | Controller driver bound; playback devices; connected monitors with audio | A monitor with audio over HDMI (probe) shows the desktop; the HDMI output plays the test sound |
| `fingerprint` | A USB reader that libfprint lists | fprintd lists it for this user; enrolled finger count; libfprint version | Three enrollments in Settings (probe: a finger is enrolled); unlock the lock screen; authorize `pkexec true` |
| `webcam` | A USB video class camera | `uvcvideo` bound; this user can open the node; PipeWire has a video source | A live picture in Camera and on a browser getUserMedia page |
| `storage` | An NVMe disk | The disk supports discard; `fstrim.timer` is enabled or `/` is mounted with discard | None |
| `input` | An internal keyboard or touchpad | Internal keyboard; a touchpad with three-finger reports; a vendor hotkey device; keyboard backlight | Three-finger gestures; the keyboard backlight key; every function key |
| `battery` | A battery with `charge_control_end_threshold` | UPower supports and enables the limit; sysfs equals UPower's end threshold; the threshold is below 100 | After resume (the limit is also re-applied at every boot, since the kernel resets it) |
| `firmware` | Always | Booted with UEFI; Secure Boot state; every firmware file the present devices need; no failed firmware load in this boot's kernel log | None |

A check that cannot read the journal (the user is not in the `wheel` or
`systemd-journal` group) says so instead of failing.

## Baselines

Results recorded on the reference machine are in [baselines/](baselines/).
