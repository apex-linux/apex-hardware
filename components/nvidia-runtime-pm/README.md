# NVIDIA runtime power management

Lets an idle NVIDIA GPU power down. This matters on hybrid laptops without a
display MUX, where an integrated GPU drives the panel and the NVIDIA GPU only
runs applications on request.

| File | Matches | Why |
| --- | --- | --- |
| `61-apex-nvidia-runtime-pm.rules` | PCI vendor `0x10de`: display, HD audio, USB xHCI and UCSI functions | The PCI core leaves runtime PM forbidden until something allows it |

The rule covers three cases: the `nvidia` driver bound (its packages ship a
similar rule, which is harmless twice), `nouveau` bound, and no driver bound
at all, as on an image without the NVIDIA flavor. Without it an unbound GPU
stays in D0 and draws power for as long as the machine runs.

## Not carried over

The previous attempt also tagged the NVIDIA DRM card `mutter-device-ignore`.
On the reference machine running GNOME 50 on Ubuntu 26.04 without that tag,
gnome-shell opens only the AMD card node and the NVIDIA render node, and the
GPU still reaches D3cold, so the tag solves nothing measured. It would also
hide displays wired to the NVIDIA GPU on other laptops.

Blacklisting `nouveau` belongs to the NVIDIA driver flavor, not to every
image; see `docs/adr/`.
