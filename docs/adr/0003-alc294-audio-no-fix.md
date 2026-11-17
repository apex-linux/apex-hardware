# ADR 0003: No audio fix for the ALC294 until a listening test fails

*   Status: proposed
*   Date: 2026-11-17
*   Decides for: this repository and `apex-image`

## Context

The reference machine has a Realtek ALC294 (`0x10ec0294`, subsystem
`0x10431ab2`) on the Ryzen HD audio controller `1022:15e3`. The previous
attempt planned a kernel patch, an HDA patch firmware and a `model=` drop-in
for silent or crackling speakers. Its own notes say the fault needed a warm
reboot from Windows, which is gone from this machine, and that the fix was
never measured.

What the running host shows (Ubuntu 26.04, kernel 7.0.0-43, 2026-11-17):

*   The kernel applies no quirk. The log has only the generic autoconfig:
    speaker on pin `0x14`, headphone on `0x21`, mic on `0x12`.
    `snd_hda_intel` has no `model` or `patch` option and the codec's
    `init_verbs` is empty.
*   The pin defaults wire an internal speaker (`0x14`, `0x90170110`), a
    headphone jack (`0x21`, `0x04211020`) and an internal digital mic
    (`0x12`, `0x90a60130`). The usual ASUS headset-mic pin `0x19` is left
    unconfigured (`0x411111f0`).
*   PipeWire offers `analog-output-speaker`, `analog-output-headphones` and
    `analog-input-mic` on the analog card, and the jack controls are
    `Headphone Jack`, `Mic Phantom Jack` and `Speaker Phantom Jack`.

Upstream, as of 2026-11-17: no kernel tree has a quirk for `1043:1ab2` or
any M7400 entry (mainline 7.4-rc3, `tiwai/sound.git` for-next,
linux-next). The ASUS ALC294 pin quirks expect the speaker on `0x17`, so
none matches and generic autoconfig is the expected result. Fedora 45 ships
kernel 7.3.4. The one public M7400QC report (Arch forums thread 281641,
2023) says speakers and headphones work, and that a headset mic on the
combo jack needed pin `0x19` retasked as a microphone.

## Decision

*   Ship **no audio fix**: no kernel patch, no patch firmware, no `model=`
    option. The previous attempt's disabled kernel patch and patch-firmware
    design are not carried over.
*   The `audio` acceptance row checks the pins and PipeWire routes
    automatically. Its manual part decides the row: both speakers from the
    correct side, the headphone jack, and a recording from the internal
    mic, after a cold boot, a warm reboot, an s2idle cycle and a runtime
    resume (the codec suspends a second after the last stream).
*   If a speaker test fails, try `options snd-hda-intel model=1043:19ce`
    (the B9450FA entry, `ALC294_FIXUP_ASUS_HPE`), then `model=1043:10d3`
    (`ALC294_FIXUP_ASUS_SPK`), as a modprobe.d file in a component keyed on
    the subsystem ID. A fix that passes goes upstream as one
    `SND_PCI_QUIRK(0x1043, 0x1ab2, ...)` line with the owner's Tested-by.
*   A headset mic on the combo jack is not in the specification's table.
    If the owner wants it, the same `ALC294_FIXUP_ASUS_HPE` quirk is the
    candidate, since it also configures pin `0x19`.

## Consequences

*   Nothing to maintain until a test fails. Fedora's kernel already gives
    the same generic configuration as the host.
*   The row is not done until someone listens; the Ubuntu baseline records
    only the automated part.

## Sources

*   `sound/hda/codecs/realtek/alc269.c` in
    <https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git>,
    <https://git.kernel.org/pub/scm/linux/kernel/git/tiwai/sound.git> and
    <https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git>
*   Fedora 45 kernel:
    <https://bodhi.fedoraproject.org/updates/?packages=kernel&releases=F45>
*   M7400QC report: <https://bbs.archlinux.org/viewtopic.php?id=281641>
*   The host measurements: [the Ubuntu baseline](../baselines/2026-11-17-ubuntu-26.04.md)
