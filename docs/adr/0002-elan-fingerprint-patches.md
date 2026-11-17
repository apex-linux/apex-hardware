# ADR 0002: Carry the ELAN 04f3:0c6e retry patches on Fedora 45

*   Status: proposed
*   Date: 2026-11-17
*   Decides for: `apex-image` (a rebuilt `libfprint`) and this repository

## Context

The reference machine's fingerprint reader, ELAN `04f3:0c6e` in the power
key, is claimed by libfprint's `elan` driver. The previous attempt wrote two
patches because the driver retries the transient pre-scan answers `0x00`
(not ready) and `0xaf` (busy or finger lifted) only on the `0x0c58` model.
On `0x0c6e` either answer ends the session with `FP_DEVICE_ERROR_PROTO`,
which fprintd reports as `enroll-disconnected`, most often during the
duplicate check before an enrollment.

Facts as of 2026-11-17:

*   **Fedora 45** ships `libfprint-1.94.100-1.fc45` and
    `fprintd-1.94.5-6.fc45`, plain upstream with no downstream patches.
    1.94.100 is the latest upstream release, and `elan.c` on master is
    identical to it.
*   `04f3:0c6e` is in the `elan` ID table with no quirk bit. On master the
    retry in `CAPTURE_READ_DATA` still applies only when
    `dev_type == ELAN_0C58` (MR !582).
*   Upstream work: MR !655 (retry the transient status on every ELAN
    device) is open, unreviewed and needs a rebase; draft MR !647 (settle
    after stop) targets `0x0c11`; MR !530 (press mode with SIGFM matching)
    is open with maintainers asking for benchmarks. Issues #402, #732,
    #759, #808, #814, #879 and #916 report this reader failing, including
    on stock Fedora 44 and 45.
*   **The Ubuntu host** runs `libfprint-2-2 1:1.95.1+tod1-0ubuntu2`.
    "1.95.1" is the libfprint-TOD fork's version, not an upstream release,
    and its `elan.c` is older than 1.94.100. fprintd lists the reader as
    "ElanTech Fingerprint Sensor", so detection works, but no finger is
    enrolled: enrollment on this host is unproven, and upstream issues #500
    and #916 report the same Ubuntu package failing on this reader.

## Decision

*   Keep both patches, `0001-elan-Retry-transient-pre-scan-status-on-04f3-0c6e`
    and `0002-elan-Bound-transient-retries-with-lift-semantics`, and rebuild
    Fedora's `libfprint` with them in `apex-image`. If a patch stops
    applying, ship Fedora's package unchanged rather than block the image.
*   Move the patches and a `series` file into this repository under
    `patches/libfprint/`, so that the fix lives next to the check that
    proves it. They are code we do not own and keep upstream's style.
*   Upstream, do not open a competing merge request. Test !655 on the
    reference machine, report the result there with the pre-scan bytes the
    patched build logs, and offer 0002's bounded retry as a follow-up on top
    of it.
*   Keep fingerprint out of PAM until enrollment passes the acceptance row
    three times in a row and verification has been measured. These patches
    fix enrollment; reports with the retry fix still describe poor
    verification in swipe mode, which only press mode (!530) addresses.

## Consequences

*   Apex carries a rebuilt `libfprint` until !655 or an equivalent lands
    and reaches Fedora. Patch 0001 stops applying when it does, which is
    the signal to drop both.
*   The `fingerprint` acceptance row passes on detection alone. Its manual
    part, three enrollments in a row, decides whether the row is done.

## Sources

*   Fedora: <https://src.fedoraproject.org/rpms/libfprint/tree/f45>,
    <https://bodhi.fedoraproject.org/updates/FEDORA-2026-0fc997c9b4>
*   libfprint: <https://gitlab.freedesktop.org/libfprint/libfprint/-/raw/master/libfprint/drivers/elan.c>,
    merge requests !655, !647, !530 and issues #879, #916 on
    <https://gitlab.freedesktop.org/libfprint/libfprint>
*   libfprint-TOD: <https://gitlab.freedesktop.org/3v1n0/libfprint>
*   The patches: `packaging/libfprint/patches/` in the archived
    `legacy-apex-kernel` repository
