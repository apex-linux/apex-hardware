# ADR 0002: Carry the ELAN 04f3:0c6e retry patches on Fedora 45

*   Status: proposed; accepted once `apex-image` ships the rebuilt
    `libfprint`
*   Date: 2026-11-17, revised for M1 the same day (fingerprint in PAM)
    and on 2026-11-18 (patch 0003, after the first install)
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

The first install on the reference machine, 2026-11-18
(`ghcr.io/apex-linux/apex:main` with `libfprint-1.94.100-1.fc45.apex`,
whose build log shows 0001 and 0002 applied), still could not enroll:

*   fprintd logged "Device reported an error during identify for enroll:
    The driver encountered a protocol error with the device." The
    identify is fprintd's duplicate check, which it runs before every
    enrollment on a device with the identify feature. On an image device
    such as `elan` it is an ordinary capture, so it is not a missing
    feature of the driver: it fails where any capture fails.
*   With 0001 and 0002 the only source of that error in a capture is the
    last branch of `CAPTURE_READ_DATA`: a pre-scan answer other than
    `0x55`, `0x00` and `0xaf`, or a read with no byte. The default journal
    does not show which; 0001 logs it at debug level only.
*   Debug logs from other `0x0c6e` units (issues #808 and #916, both
    without 0001) show when it happens: a capture that starts soon after
    the previous one, with the finger still on the key while calibration
    takes the background. Calibration then accepts a delta of 170 to 225
    instead of about 30, and the next pre-scan read answers something
    other than `0x55` after most of a second.
*   The second message, "Device was already claimed", follows from the
    first: fprintd keeps the claim until the client releases it or leaves
    the bus, and GNOME Settings claimed again without releasing. Closing
    Settings frees the reader.

## Decision

*   Keep the patches `0001-elan-Retry-transient-pre-scan-status-on-04f3-0c6e`
    and `0002-elan-Bound-transient-retries-with-lift-semantics`, and rebuild
    Fedora's `libfprint` with them in `apex-image`. If a patch stops
    applying, ship Fedora's package unchanged rather than block the image.
*   Add `0003-elan-Never-fail-a-04f3-0c6e-capture-on-its-pre-scan-answer`:
    on `0x0c6e`, every other pre-scan answer, and an empty read, takes
    0002's path for `0x00` and `0xaf`. After a frame it ends the capture
    as a lift; before one it is retried with the same back-off, and a run
    ends after the command timeout as a read timeout would. fprintd then
    asks for another swipe instead of reporting the device as
    disconnected. The first such answer of a run is logged as a warning,
    so the next journal from the machine names the byte.
*   Move the patches and a `series` file into this repository under
    `patches/libfprint/`, so that the fix lives next to the check that
    proves it. They are code we do not own and keep upstream's style.
*   Upstream, do not open a competing merge request. Test !655 on the
    reference machine, report the result there with the pre-scan bytes the
    patched build logs, and offer 0002's bounded retry as a follow-up on top
    of it.
*   Turn fingerprint on in PAM in the image (authselect's
    `with-fingerprint` feature, so that `gdm-fingerprint`, `polkit-1` and
    `sudo` accept a finger). The M1 row is "enroll, unlock, authorize", and
    its unlock and authorize steps cannot pass otherwise. Fedora's default
    `local` profile leaves the feature off; only an interactive Anaconda
    install turns it on. The risk is small: `pam_fprintd` steps aside when
    the user has no finger enrolled, and the password stays the fallback.
    These patches fix enrollment; reports with the retry fix still describe
    poor verification in swipe mode, which only press mode (!530)
    addresses, so the row's unlock step is the measurement that decides
    whether verification is good enough.

## Consequences

*   Apex carries a rebuilt `libfprint` until !655 or an equivalent lands
    and reaches Fedora. Patch 0001 stops applying when it does, which is
    the signal to drop the series.
*   0003 trades a protocol error for at most ten seconds of retries per
    capture. If the byte it logs turns out to mean the sensor needs a new
    background, the fix belongs in calibration instead, and 0003 shrinks
    to that byte.
*   The `fingerprint` row passes only when three enrollments, an unlock and
    an authorization all succeed. Its probes report a missing
    `with-fingerprint` as the reason when unlock or authorize fail.

## Sources

*   Fedora: <https://src.fedoraproject.org/rpms/libfprint/tree/f45>,
    <https://bodhi.fedoraproject.org/updates/FEDORA-2026-0fc997c9b4>
*   libfprint: <https://gitlab.freedesktop.org/libfprint/libfprint/-/raw/master/libfprint/drivers/elan.c>,
    merge requests !655, !647, !530 and issues #808, #879, #916 on
    <https://gitlab.freedesktop.org/libfprint/libfprint>
*   libfprint-TOD: <https://gitlab.freedesktop.org/3v1n0/libfprint>
*   The patches: `packaging/libfprint/patches/` in the archived
    `legacy-apex-kernel` repository
*   fprintd 1.94.5: `enroll_identify_cb()` and the claim check in
    `src/device.c`, <https://gitlab.freedesktop.org/libfprint/fprintd>
