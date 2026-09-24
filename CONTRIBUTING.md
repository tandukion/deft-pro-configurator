# Contributing

Contributions are welcome.

## Development setup

On Ubuntu, install the runtime libraries used by the application:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 python3-evdev udev
```

Run the unit tests with:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Build the Debian package with:

```bash
./tools/build-deb.sh
```

The package will be written to `dist/`.

## Pull requests

Please keep changes focused, update the README when user-visible behavior changes, and add tests for changes to configuration or mapping logic where practical.
