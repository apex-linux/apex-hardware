# Firmware list

`firmware.txt` names, for each device, the firmware files it needs before it
works. It installs to `/usr/share/apex-hardware/firmware.txt`.

*   `apex-image` checks at build time that every line matches a file in the
    image, so a packaging change that drops a firmware file fails the build
    instead of a device on a laptop.
*   The acceptance check `firmware` checks the lines whose device is present.

Add a line when a device is known to fail without a file, with a comment
that names the device. The format is described at the top of the file.
