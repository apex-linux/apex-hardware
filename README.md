# apex-hardware

Holds the hardware rules for Apex Linux, keyed by device, and the checks
that prove each device works.

Part of [Apex Linux](https://github.com/apex-linux/apex). See the
[specification](https://github.com/apex-linux/apex/blob/main/docs/spec.md)
and the
[engineering standards](https://github.com/apex-linux/apex/blob/main/docs/engineering.md).

## What it produces

`just install <destdir>` installs files under `<destdir>/usr` and nowhere
else. [apex-image](https://github.com/apex-linux/apex-image) calls it while
it builds the image.

Each directory in `components/` covers one device class, for example hybrid
graphics or a vendor's battery interface. It holds a `README.md` that says
which hardware it matches and why each file exists, and a `usr/` tree that
is copied into the image as it is.

## Building and testing

You need [`just`](https://github.com/casey/just) and
[`uv`](https://docs.astral.sh/uv/). `uv` installs Python 3.14 and every
linter that the recipes use.

```bash
just lint
just test
just install build/root
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
