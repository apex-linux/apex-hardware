# libfprint patches

Two patches to libfprint's `elan` driver for the ELAN `04f3:0c6e` reader
(the power key of the ASUS Vivobook Pro 14X M7400QC and its siblings).
[ADR 0002](../../docs/adr/0002-elan-fingerprint-patches.md) explains why
they are still needed on Fedora 45.

| Patch | Effect |
| --- | --- |
| `0001-elan-Retry-transient-pre-scan-status-on-04f3-0c6e` | Gives `0x0c6e` its own quirk bit and retries the transient pre-scan answers `0x00` and `0xaf`, as upstream does for `0x0c58` only, instead of ending the session with a protocol error. Logs each pre-scan answer at debug level. |
| `0002-elan-Bound-transient-retries-with-lift-semantics` | Bounds those retries to the command timeout. On `0x0c6e`, a transient answer after the first frame means the finger was lifted, so the capture ends and the image is submitted. |

`series` lists them in order. `apex-image` rebuilds Fedora's `libfprint`
source package with them; if one stops applying, it ships Fedora's package
unchanged rather than fail the image.

Both apply cleanly to upstream tag `v1.94.100` (checked on 2026-11-17,
`elan.c` sha256 `b6e02523…3307b`). They are code we do not own: they follow
libfprint's style, and changes go upstream through merge request !655.

The previous attempt also carried two disabled patches, `0101` (recover
from a frame darker than the background) and `0102` (settle after stop).
They stay in the archived `legacy-apex-kernel` repository until a log from
the reference machine shows their trigger.
