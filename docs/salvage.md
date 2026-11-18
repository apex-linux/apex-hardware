# What came over from the previous attempt

The previous attempt's hardware files, in the archived `apex-image`,
`apex-system` and `apex-kernel` repositories, were reviewed twice: when this
repository started, and again for M1 on 2026-11-17. A file is carried over
only when a check shows that a row needs it. The previous attempt keyed
everything to one machine's profile (`hardware/m7400qc/profile.toml`); what
is carried over is keyed by device ID, vendor or driver instead.

Each entry names the check that would reopen it: if that check fails on an
installed Apex, the dropped file is the first thing to try.

| Previous file | Fate | Why | Reopened by |
| --- | --- | --- | --- |
| `apex-image` `61-apex-dgpu-pm.rules`, `variants/pair/61-apex-dgpu.rules` | Carried over as `components/nvidia-runtime-pm` | The PCI core forbids runtime PM until something allows it; without the rule an unbound GPU stays in D0. Keyed by vendor `0x10de` and PCI class, not by `25a2`, so it covers every function and every NVIDIA laptop | `dgpu` |
| `apex-image` `61-apex-battery.rules` | Carried over as `components/battery-charge-limit` | `asus-nb-wmi` adds the threshold attribute without a uevent, so UPower never sees it. Keyed by the driver, not by `BAT0` | `battery` |
| `apex-image` `tmpfiles.d/apex-upower.conf` | Carried over, same component | The specification wants the 80% limit on by default; UPower applies it at start only when this flag holds `1` | `battery` |
| `apex-image` `kargs.d/10-apex.toml`, `modprobe.d/apex-dgpu.conf` (nouveau blacklist) | Moved to `flavors/nvidia` | Only the NVIDIA flavor needs `nouveau` and `nova_core` kept off; the base image keeps `nouveau` for GPUs without the flavor | `dgpu` on the flavor |
| `apex-image` `kargs.d/10-apex.toml` (`rhgb`, `quiet`, `panic=10`, `systemd.ssh_auto=no`) | Not hardware | Boot policy; belongs to `apex-image` | None |
| `apex-image` `upower.service.d/10-apex-wait-threshold.conf` | Dropped | It waited for the old `CHARGE_LIMIT` rule. UPower 1.91.2 and later import the limit from upstream's own hwdb, and Fedora 45 ships 1.91.5; the battery rule above re-runs that import once the attribute exists | `battery` |
| `apex-image` `udev` `CHARGE_LIMIT` lines | Dropped | Upstream since UPower 1.91.2 | `battery` |
| `apex-image` `/etc/tuned/ppd.conf`, `tuned/profiles/apex-performance` | Dropped | A preference, not a hardware need: Fedora's `throughput-performance` already sets the `performance` EPP and platform profile, and the server tunables it adds are not a row of the table. It also lives in `/etc`, which this repository never writes | `cpu` (the power mode steps check the profile, the EPP and `platform_profile`) |
| `apex-image` `variants/pair/modprobe.d/apex-nvidia.conf` (`NVreg_DynamicPowerManagement=0x02`) | Dropped | The driver's default picks fine-grained runtime D3 on notebooks; the check reads the driver's own status | `dgpu` (fails unless runtime D3 is `Enabled`) |
| `apex-image` `variants/pair/kargs.d/20-apex-pair.toml` (`module.sig_enforce=1`, `zswap.enabled=0`) | Dropped | Belonged to the custom kernel pair, which the specification rules out; Secure Boot is off for M1 | None |
| `apex-image` `journald.conf.d/10-apex-persistent.conf` | Not hardware | The checks read only this boot's journal, which a volatile journal also has | None |
| `apex-system` `61-apex-mutter-ignore-dgpu.rules` | Dropped | Measured without it: gnome-shell opens only the AMD card and the NVIDIA render node, and the GPU still reaches D3cold. It would also hide displays wired to the NVIDIA GPU on other laptops | `dgpu` (the idle reading and "powers down after the app") |
| `apex-system` `monitors.xml`, `profile.toml` `[panel]` | Not hardware | Scale 2 is a desktop default; `apex-desktop` sets it, and the `display` row checks it | `display` |
| `apex-system` `hardware/m7400qc/audio/` (`coef-dump.sh`, `try-fix.sh`, the HDA patch firmware) | Dropped | The fault it chased needed a warm reboot from Windows, and the fix was never measured; [ADR 0003](adr/0003-alc294-audio-no-fix.md) | `audio` (the speaker step) |
| `apex-kernel` `0001-ALSA-hda-realtek-Fix-speaker-output-on-ASUS-M7400QC.patch` | Dropped | Same; Apex ships Fedora's kernel | `audio` |
| `apex-kernel` libfprint `0001`, `0002` | Carried over as `patches/libfprint`, with a new `0003` | Fedora 45's libfprint still ends a session on the reader's transient answers, and the first install showed a further answer that 0002 does not cover; [ADR 0002](adr/0002-elan-fingerprint-patches.md) | `fingerprint` (the enroll step) |
| `apex-kernel` libfprint `0101`, `0102` | Left in the archive | Disabled there, for faults nobody has logged on this reader | `fingerprint` |

## What only an installed Apex can show

The drops above rest on measurements from the Ubuntu host or on upstream
sources. Three of them need the installed system to confirm:

*   **No driver or `nouveau` on the dGPU** (the base image, without the
    NVIDIA flavor): whether the GPU reaches D3cold with `nouveau` bound has
    not been measured. A `dgpu` run on the base image answers it.
*   **tuned-ppd's mapping**: whether Fedora's default `ppd.conf` moves
    `platform_profile` with each power mode, and follows Fn+F5. The `cpu`
    power mode steps answer it.
*   **UPower 1.91.5 on kernel 7.3**: whether the limit is back at 80 after
    each boot. Every `battery` run on an installed system answers it.
