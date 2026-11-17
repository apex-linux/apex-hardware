# Battery charge limit

Turns the battery charge limit on by default and makes UPower see it on
ASUS laptops. UPower 1.91.2 and later, which Fedora 45 ships as 1.91.5,
support batteries with only an end threshold; its hwdb sets the limit to
80% everywhere.

| File | Matches | Why |
| --- | --- | --- |
| `61-apex-asus-battery.rules` | The `asus-nb-wmi` driver | Its threshold file appears after the battery's udev event, so UPower's rule can miss it |
| `apex-charge-limit.conf` | Any battery UPower supports | The limit is off unless UPower's state file says `1` |

Kernels 7.2 and 7.3 reset the ASUS threshold to 100 at every boot, and
UPower writes it again when it starts. The embedded controller keeps it
across suspend. The `battery` acceptance check covers both: run it after a
reboot and after a resume.

## Not carried over

*   A `CHARGE_LIMIT` rule for end-only batteries: UPower 1.91.2 added it.
*   A drop-in that made `upower.service` wait up to ten seconds for the
    threshold: nothing measured shows UPower starting before udev has run
    the change event above. If the `battery` check fails after a cold boot,
    this is the first thing to revisit.
