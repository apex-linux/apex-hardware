# nouveau blacklist (nvidia flavor)

Keeps `nouveau` and `nova_core` off the NVIDIA GPU, in the initramfs and in
the running system, so that the `nvidia` open kernel module binds it.

| File | Matches | Why |
| --- | --- | --- |
| `10-apex-nvidia.toml` | Machines booting the nvidia flavor | Driver packages cannot set kernel arguments in a container build |

The flavor's driver packages (negativo17) bring the module, its udev and
modprobe.d settings, and the userspace; see
[ADR 0001](../../../docs/adr/0001-nvidia-image-flavor.md).
