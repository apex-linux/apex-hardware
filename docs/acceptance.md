# Acceptance checks

One check per row of the
[reference machine table](https://github.com/apex-linux/apex/blob/main/docs/spec.md#reference-machine).
A row is done when its check passes on the machine, not when a fix is
written.

## Run book

For the owner, on the M7400QC with Apex installed. One full run takes
about twenty minutes, most of it the guided steps. The M1 exit is a record
from such a run in which every row is `PASS`.

### Before the run

1.  **Be on the NVIDIA flavor.** The `dgpu` row needs the NVIDIA driver,
    so install or switch to the image tag that `apex-image` publishes for
    the flavor, `main-nvidia`, then reboot:

    ```bash
    sudo bootc switch ghcr.io/apex-linux/apex:main-nvidia
    ```

    The record's "NVIDIA module" line shows the driver version; "not
    loaded" means the machine is on the base image.
2.  **Keep Secure Boot off** in the firmware setup. The flavor's module is
    unsigned until M3, and with Secure Boot on it does not load.
3.  **Have at hand:** wired headphones; Bluetooth headphones and a Bluetooth
    mouse or keyboard; a display with speakers (a TV works) and an HDMI
    cable; a Wi-Fi network with internet access, for the camera page in
    Firefox.
4.  **The apps the steps open** are all in the image as RPMs, with no
    Flatpak needed: Settings (`gnome-control-center`), Text Editor
    (`gnome-text-editor`), Camera (`snapshot`) and Firefox (`firefox`).
5.  **Start from a fresh boot:** power off, power on, log in to GNOME as
    your own user (not root), connect to Wi-Fi, and unplug the headphones
    and the HDMI cable. Leave the machine idle for a minute, so that the
    discrete GPU is asleep when the run starts.

### The run

Open Terminal and run:

```bash
apex-accept
```

It first runs every automated check, which takes about half a minute and
needs nothing from you. Then it asks you, one step at a time:

1.  **Suspend and wake** once from the system menu, then press Enter. It
    checks that the suspend reached hardware sleep and measures `dgpu`,
    `cpu`, `wifi` and `battery` again.
2.  **The guided steps** for each row, in table order: open an app on the
    discrete GPU and close it; switch the three power modes; move the
    brightness slider; pair Bluetooth devices; test the speakers, the
    headphone jack and the microphone in Settings; connect the HDMI
    display; enroll a finger three times, unlock with it and authorize
    `pkexec true` with it; look at Camera and the camera page in Firefox; and
    try the gestures, the keyboard backlight and the function keys.

Each step says what to do. When it shows `[Enter when done, s to skip]`,
do it and press Enter; a check then runs on its own. When it asks
`[y/n/s]`, answer what you saw or heard: `y`, `n`, or `s` to skip. Answer
`n` whenever something was wrong, even slightly; the record keeps your
answer next to the question.

At the end it prints one line per row and writes the record:

*   `PASS`: the automated check and every step passed.
*   `FAIL`: something failed; the line starts with what.
*   `TODO`: a step was skipped or not answered.
*   `SKIP`: the machine lacks that hardware (none should on the M7400QC).

A skipped step leaves its row at `TODO`; run `apex-accept` again from the
start to finish it, since only a run of every row writes a record.

### Sending the record back

The run prints where it wrote the record, for example
`~/apex-acceptance/2026-11-20-apex-45.md` and its `.json`. Send back both
files unchanged, whatever the result: a failing record is evidence too.
Either add them to `docs/records/` in a pull request to this repository,
titled "Record the 2026-11-20 acceptance run on Apex 45", or hand them to
the session that maintains this repository, which commits them that way.

### When a row fails

The record says why. The usual first moves:

*   `dgpu` with "runtime D3 is Disabled": the NVIDIA module lacks the
    Linux 7.3 fix ([ADR 0001](adr/0001-nvidia-image-flavor.md)); this is an
    image problem, not a setting.
*   `fingerprint` with "does not use pam_fprintd": the image did not turn
    on authselect's `with-fingerprint` ([ADR 0002](adr/0002-elan-fingerprint-patches.md)).
*   `audio` with "no" on the speakers: [ADR 0003](adr/0003-alc294-audio-no-fix.md)
    lists the two `model=` options to try next.
*   `battery` at 100%: `cat /var/lib/upower/charging-threshold-status`
    should print `1`; if it does, UPower did not see the threshold, and
    `udevadm info /sys/class/power_supply/BAT0 | grep CHARGE_LIMIT` shows
    whether its rule ran.
*   Anything else: send the record as it is.

### Optional: the base image

A second run on the base image (`ghcr.io/apex-linux/apex:main`, no NVIDIA
driver) answers whether the discrete GPU also reaches D3cold with `nouveau`
([salvage](salvage.md#what-only-an-installed-apex-can-show)). It is not
part of the M1 exit; its `dgpu` row is the only one that matters.

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
| `cpu` | Always | cpufreq driver, governor and EPP; a power profile on D-Bus; s2idle or deep offered; no failed suspend this boot; the last s2idle reached hardware sleep | After resume; Performance, Power Saver and Balanced from Quick Settings (probe each: the active profile, the EPP, and `platform_profile` following it) |
| `igpu` | The `boot_vga` GPU | Driver bound; a connected display; the session is Wayland | None |
| `dgpu` | Any other display controller | `power/control` is `auto`; runtime-suspended within 15 s; `D3cold`; suspended share since boot; with `nvidia` bound, the driver's runtime D3 status is `Enabled` and its power parameters | After resume; an app launched on the discrete GPU wakes it (probe) and draws; it powers down again once closed (probe) |
| `display` | A connected eDP, LVDS or DSI connector | The panel runs its largest mode at its highest refresh rate; backlight control; scale 2 on the reference panel (SDC `0x4154`) | The brightness slider dims and brightens the panel |
| `wifi` | A wireless interface | Driver bound; NetworkManager connected | After resume, connected again within 30 s |
| `bluetooth` | An HCI controller | Driver bound; its rfkill not blocked; powered; paired device count | Headphones and a mouse or keyboard connected (probe); sound and input work |
| `audio` | An analog HD audio codec | Pins wire an internal speaker, a headphone jack and an internal mic; PipeWire offers speaker and headphone routes and an analog input | Speakers left and right; headphones detected in the jack (probe) and playing; the internal mic's input level moves |
| `hdmi_audio` | An HDMI or DisplayPort codec | Controller driver bound; playback devices; connected monitors with audio | A monitor with audio over HDMI (probe) shows the desktop; the HDMI output plays the test sound |
| `fingerprint` | A USB reader that libfprint lists | fprintd lists it for this user; enrolled finger count; libfprint version | Three enrollments in Settings (probe: a finger is enrolled); unlock the lock screen (probe: `gdm-fingerprint` reaches `pam_fprintd`); authorize `pkexec true` (probe: `polkit-1` reaches `pam_fprintd`) |
| `webcam` | A USB video class camera | `uvcvideo` bound; this user can open the node; PipeWire has a video source | A live picture in Camera and on a getUserMedia page in Firefox |
| `storage` | An NVMe disk | The disk supports discard; `fstrim.timer` is enabled or `/` is mounted with discard | None |
| `input` | An internal keyboard or touchpad | Internal keyboard; a touchpad with three-finger reports; a vendor hotkey device; keyboard backlight | Three-finger gestures; the keyboard backlight key; every function key |
| `battery` | A battery with `charge_control_end_threshold` | UPower supports and enables the limit; sysfs equals UPower's end threshold; the threshold is below 100 | After resume (the limit is also re-applied at every boot, since the kernel resets it) |
| `firmware` | Always | Booted with UEFI; Secure Boot state; every firmware file the present devices need; no failed firmware load in this boot's kernel log | None |

A check that cannot read the journal (the user is not in the `wheel` or
`systemd-journal` group) says so instead of failing.

## Records and baselines

Runs on an installed Apex are in [records/](records/). Results from the
previous system, measured before Apex, are in [baselines/](baselines/).
