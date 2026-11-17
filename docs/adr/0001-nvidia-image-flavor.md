# ADR 0001: NVIDIA driver as an image flavor built from negativo17

*   Status: proposed
*   Date: 2026-11-17
*   Decides for: `apex-image` (the flavor build) and this repository (its
    rules and checks)

## Context

M1 needs the NVIDIA driver as prebuilt modules in an image flavor, so that
machines without NVIDIA do not carry it. The reference machine is an
Optimus laptop without a MUX: the AMD iGPU drives the panel and HDMI, and
the RTX 3050 Mobile (`10de:25a2`, one PCI function) runs applications on
request and must otherwise sit in D3cold.

Facts as of 2026-11-17:

*   Fedora 45 runs kernel 7.3: `quay.io/fedora/fedora-bootc:45` from
    2026-11-16 carries 7.3.3-300.fc45, and 7.3.4 is already stable in
    Bodhi. The current NVIDIA branch is 620.70.06.
*   **No repository ships kernel modules prebuilt per Fedora kernel.**
    negativo17 and RPM Fusion ship akmods (negativo17 also DKMS); NVIDIA's
    CUDA repository has DKMS for Fedora 44 and no driver for 45 yet.
*   **Universal Blue** builds them: `ghcr.io/ublue-os/akmods-nvidia-open`
    tag `main-45` runs `akmods --force --kernels <kver>` on negativo17's
    `akmod-nvidia` in a builder stage, signs the modules with Universal
    Blue's key, and publishes the kmod RPMs with the kernel they match.
*   **Linux 7.3 breaks runtime D3** in the unpatched open module, which then
    reports "Runtime D3 status: Disabled by default", so the GPU never
    powers down. negativo17 carries the fix since `nvidia-kmod`
    620.70.06-2 (2026-11-12). RPM Fusion's 620.70.06-1 does not.
*   negativo17's packages are open-module only, are meant to be installed
    in images that may boot without NVIDIA (no presets; `nvidia-powerd`
    and `nvidia-persistenced` start from udev only when a GPU exists), and
    rely on the kernel suspend notifiers that are the driver default since
    615.71.09. Their `%post` cannot set kernel arguments in a container
    build.
*   On Ubuntu with 595.99.02 the reference GPU already reaches D3cold with
    fine-grained runtime D3 (see the baseline), so the hardware is capable.

## Decision

Build the flavor in `apex-image` from **negativo17**, with Apex building
and signing the kernel module itself:

1.  A builder stage from the same base image digest reads the kernel
    version with `rpm -q kernel-core`, installs `akmod-nvidia` and the
    matching `kernel-devel`, and runs `akmods --force --kernels "${kver}"`
    with the Apex module signing key from a build secret. Building outside
    a bootc-marked root avoids rhbz#2459819.
2.  The flavor stage installs that `kmod-nvidia` and the userspace from the
    same negativo17 snapshot. The build fails unless `modinfo -F vermagic`
    names the image's kernel and the kmod version equals `nvidia-driver`.
3.  Settings: negativo17's shipped `modprobe.d/nvidia.conf` and
    `60-nvidia.rules` unchanged. Driver defaults for
    `DynamicPowerManagement` (3, fine-grained on Ampere notebooks) and
    `UseKernelSuspendNotifiers` (1). No `nvidia-suspend`, `-resume` or
    `-hibernate` units; `nvidia-persistenced` is not enabled; NVIDIA
    modules stay out of the initramfs.
4.  This repository adds, for the flavor only,
    `/usr/lib/bootc/kargs.d/10-apex-nvidia.toml` with
    `rd.driver.blacklist=nouveau,nova_core` and
    `modprobe.blacklist=nouveau,nova_core`, and the acceptance check gains
    the driver's view: `Runtime D3 status: Enabled (fine-grained)` and
    `UseKernelSuspendNotifiers: 1`.

Universal Blue's prebuilt image is the fallback if the builder stage costs
too much in CI. Using it means checking that its kernel label equals the
base image's, and asking users to enroll Universal Blue's key instead of
Apex's when Secure Boot comes.

Suspend: negativo17 sets `NVreg_EnableS0ixPowerManagement=1`; Ubuntu runs
with 0. Keep negativo17's value, measure an s2idle cycle with the `cpu` and
`dgpu` checks before and after, and ship
`options nvidia NVreg_EnableS0ixPowerManagement=0` from this repository
only if resume fails.

## Consequences

*   The base image keeps `nouveau` available. With no driver bound, or with
    `nouveau`, `61-apex-nvidia-runtime-pm.rules` lets the GPU reach D3cold.
    That path is not yet measured on this machine.
*   Each kernel update in the base image rebuilds the module; a rebuild that
    fails blocks the flavor, not the base image.
*   Apex owns a module signing key. Secure Boot remains off for M1 as the
    specification says; the key is what makes turning it on later possible.
*   The 7.3 runtime D3 fix lives in negativo17 until NVIDIA ships it. The
    `dgpu` check catches a release that loses it.

## Sources

*   NVIDIA README 620.70.06, chapters 20 to 22:
    <https://download.nvidia.com/XFree86/Linux-x86_64/620.70.06/README/dynamicpowermanagement.html>
*   negativo17: <https://negativo17.org/nvidia-driver/>,
    <https://github.com/negativo17/nvidia-kmod>,
    <https://github.com/negativo17/nvidia-kmod-common>
*   RPM Fusion: <https://rpmfusion.org/Howto/NVIDIA>,
    <https://github.com/rpmfusion/nvidia-kmod>
*   Universal Blue: <https://github.com/ublue-os/akmods>,
    <https://github.com/ublue-os/bluefin/blob/main/build_files/base/03-install-kernel-akmods.sh>
*   Fedora proof of concept: <https://github.com/coreos/fedora-bootc-nvidia>
*   bootc kernel arguments:
    <https://github.com/bootc-dev/bootc/blob/main/docs/src/building/bootc-kernel-arguments.7.md>
*   akmods in bootc builds: <https://bugzilla.redhat.com/show_bug.cgi?id=2459819>
