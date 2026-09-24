# DEFT Pro Configurator

A GTK desktop application for configuring and remapping the **Elecom DEFT Pro trackball** on Ubuntu/Linux.

The application provides a GUI for assigning actions to the DEFT Pro's logical buttons and runs the remapper through Linux **evdev/uinput**. This means the configured mappings are not tied to `xinput` and can be used from both X11 and Wayland sessions, subject to the normal desktop/security restrictions around synthetic input.

> **Hardware note:** This project is intended for the Elecom DEFT Pro. The repository contains the DEFT Pro-specific button mapping used by the application, but physical-device testing is still recommended after installation.

## Features

- GUI configuration for B1–B12.
- Covers left/middle/right click, wheel, wheel tilt, side buttons, and Fn1/Fn2/Fn3.
- Actions:
  - pass through the original input
  - disable a button
  - emit another mouse button
  - emit a keyboard key
  - emit a keyboard shortcut / hotkey
  - launch a shell command
  - generate vertical or horizontal scroll events
- Profiles with create, duplicate, delete, and manual switching.
- Physical-button learning: select **Learn physical button…**, then press a DEFT Pro button.
- Background remapping daemon using `python3-evdev` and `/dev/uinput`.
- Per-user systemd service for automatic startup.
- udev rules using `uaccess` so the active desktop user can access the input device.
- Debian package build script.
- Unit tests for configuration handling.

## Repository layout

```text
.
├── README.md
├── CONTRIBUTING.md
├── VERSION
├── pyproject.toml
├── .gitignore
├── .github/
│   └── workflows/
│       └── test.yml
├── assets/
│   └── deft-pro-configurator.svg
├── docs/
│   └── configuration.md
├── packaging/
│   └── deb/
│       ├── DEBIAN/
│       │   ├── control
│       │   ├── postinst
│       │   └── prerm
│       ├── etc/
│       │   ├── modules-load.d/
│       │   │   └── deft-pro-configurator.conf
│       │   └── udev/rules.d/
│       │       └── 70-deft-pro-configurator.rules
│       └── usr/
│           ├── bin/
│           │   ├── deft-pro-configurator
│           │   └── deft-pro-daemon
│           ├── lib/systemd/user/
│           │   └── deft-pro-daemon.service
│           └── share/
│               ├── applications/
│               │   └── deft-pro-configurator.desktop
│               └── icons/hicolor/scalable/apps/
│                   └── deft-pro-configurator.svg
├── src/
│   └── deft_pro/
│       ├── __init__.py
│       ├── config.py
│       ├── engine.py
│       └── gui.py
├── tests/
│   └── test_config.py
└── tools/
    └── build-deb.sh
```

`src/` is the source of truth for the Python application. The files under `packaging/deb/` are Debian package metadata and integration files only.

## Requirements

For the packaged application, Ubuntu must provide:

- Python 3.8 or newer
- GTK 3 introspection (`python3-gi`, `gir1.2-gtk-3.0`)
- `python3-evdev`
- `udev`
- Linux `/dev/uinput`

The Debian package declares these runtime dependencies, so `apt` normally installs them automatically.

## Installation

### Option 1: install a prebuilt `.deb`

From a downloaded release:

```bash
sudo apt install ./deft-pro-configurator_1.0.0_all.deb
```

Using `apt` instead of `dpkg -i` is recommended because `apt` can resolve the package dependencies.

After installation, open **DEFT Pro Configurator** from the Ubuntu application menu.

The package also enables the user-level `deft-pro-daemon.service` globally so it can start automatically with graphical user sessions.

### Option 2: build the `.deb` from this repository

Install the build/runtime prerequisites first:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 python3-evdev udev dpkg-dev
```

Then build:

```bash
./tools/build-deb.sh
```

The resulting package is written to:

```text
dist/deft-pro-configurator_1.0.0_all.deb
```

Install it with:

```bash
sudo apt install ./dist/deft-pro-configurator_1.0.0_all.deb
```

### First-run permissions

The package installs a udev rule for the DEFT Pro and `/dev/uinput`. On most Ubuntu desktop sessions the `uaccess` rule takes effect without additional group configuration.

If the application reports a permission error immediately after installation, log out and back in, then check the daemon status as described in the troubleshooting section below.

## Usage

1. Connect the DEFT Pro.
2. Launch **DEFT Pro Configurator** from the application menu.
3. The top-right status indicator should show the connected device.
4. Select a button in the left-hand grid.
5. Choose an action type.
6. Configure the action parameters.
7. Click **Apply changes**.
8. Test the physical button.

### Learning a physical button

When the DEFT Pro's physical numbering is unclear:

1. Select the button you want to configure.
2. Click **Learn physical button…**.
3. Press the physical DEFT Pro button.
4. The GUI switches to the logical button detected by the daemon.

This is particularly useful for Fn1/Fn2/Fn3 and for checking a device/firmware-specific layout.

### Profiles

Profiles allow different mappings for different workflows. The current release supports **manual profile selection**.

Use the Profile controls to:

- **New** — create a profile from the current mapping.
- **Duplicate** — copy the current profile.
- **Delete** — remove the current profile, leaving at least one profile.

The selected profile is persisted as part of the user configuration and is reloaded by the daemon.

Automatic per-application profile switching is **not** included in this release.

### Common ergonomic preset

The GUI includes **Apply common ergonomic preset**, which assigns:

```text
Fn1 → left click
Fn2 → middle click
Fn3 → right click
```

This is only a starting point; edit or reset the individual buttons as needed.

## Configuration and data files

The application stores user-specific data under:

```text
~/.config/deft-pro/
```

Important files:

```text
~/.config/deft-pro/config.json   # persistent button mappings and profiles
~/.config/deft-pro/state.json    # current daemon status for the GUI
~/.config/deft-pro/daemon.sock   # GUI ↔ daemon local control socket
```

The configuration file is JSON and is written atomically to reduce the chance of a partial file after a crash.

See [`docs/configuration.md`](docs/configuration.md) for the structure and examples.

### System-level integration files

The package installs:

```text
/etc/udev/rules.d/70-deft-pro-configurator.rules
/etc/modules-load.d/deft-pro-configurator.conf
/usr/lib/systemd/user/deft-pro-daemon.service
/usr/bin/deft-pro-configurator
/usr/bin/deft-pro-daemon
```

The daemon uses the physical DEFT Pro input device and creates a virtual pointer through `/dev/uinput`.

## Starting/stopping the daemon manually

Normal operation should not require this, but it is useful for troubleshooting.

Check status:

```bash
systemctl --user status deft-pro-daemon.service
```

Start:

```bash
systemctl --user start deft-pro-daemon.service
```

Stop:

```bash
systemctl --user stop deft-pro-daemon.service
```

Restart:

```bash
systemctl --user restart deft-pro-daemon.service
```

Follow logs:

```bash
journalctl --user -u deft-pro-daemon.service -f
```

## Uninstallation

### Remove the package

```bash
sudo apt remove deft-pro-configurator
```

### Remove package and Debian-managed configuration files

```bash
sudo apt purge deft-pro-configurator
```

The per-user JSON configuration is intentionally not removed by `apt remove` or `apt purge`, because Debian package removal does not normally manage files in a user's home directory.

To remove your DEFT Pro Configurator user data too:

```bash
rm -rf ~/.config/deft-pro
```

To remove the package's build output from a source checkout:

```bash
rm -rf .build dist
```

## Troubleshooting

### The GUI says the DEFT Pro is not detected

Check whether Linux sees an input device:

```bash
ls -l /dev/input/by-id/
```

Then inspect the daemon status:

```bash
systemctl --user status deft-pro-daemon.service
```

And the recent logs:

```bash
journalctl --user -u deft-pro-daemon.service --no-pager -n 100
```

### The daemon reports a permission error

Check `/dev/uinput`:

```bash
ls -l /dev/uinput
```

Reload udev rules after installation if needed:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Then log out/in again and retry.

### The original DEFT Pro behaves normally only when the daemon is stopped

That is expected while the remapper is active: the daemon grabs the physical device, consumes its events, and emits equivalent events through the virtual uinput device.

Stop the daemon to return the physical device to normal direct input:

```bash
systemctl --user stop deft-pro-daemon.service
```

### A mapping does not work as expected

Use **Learn physical button…** to confirm the physical-to-logical mapping first. The application intentionally uses a DEFT Pro-specific logical mapping rather than assuming Linux button numbers correspond one-to-one with the GUI labels.

### Reset all mappings

The safest GUI method is to select each button and choose **Pass through**, or delete and recreate the profile.

For a complete configuration reset:

```bash
rm -f ~/.config/deft-pro/config.json
```

Then restart the daemon or reopen the GUI:

```bash
systemctl --user restart deft-pro-daemon.service
```

## Security considerations

The **Launch command** action executes the configured command in the user's desktop session. Treat mappings as executable configuration: only put commands you trust into `config.json` or through the GUI.

The daemon uses a Unix-domain socket at `~/.config/deft-pro/daemon.sock` with mode `0600`, so normal GUI control is limited to the same user.

## Development

Run the unit tests:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Build the Debian package:

```bash
./tools/build-deb.sh
```

The GitHub Actions workflow in `.github/workflows/test.yml` runs the configuration tests on pushes and pull requests.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the development workflow.

## Release checklist

Before publishing a GitHub release:

1. Replace the placeholder maintainer email in `packaging/deb/DEBIAN/control`.
2. Update `VERSION`.
3. Update the version in `pyproject.toml` if a Python package release is also being published.
4. Update `packaging/deb/DEBIAN/control` if other metadata changed; `tools/build-deb.sh` replaces its `Version:` field automatically.
5. Run the unit tests.
6. Build the `.deb`.
7. Install the newly built `.deb` on a clean Ubuntu machine and test the actual DEFT Pro hardware.
8. Commit the source and tag the release.

## Known limitations

- Physical hardware testing is required to validate every DEFT Pro firmware/device revision.
- Automatic application-specific profile switching is not implemented.
- The daemon currently selects the best matching trackball-like input device; systems with multiple similar pointer devices should verify the selected device in the GUI/logs.
- The project currently targets GTK 3 because that matches the Ubuntu Python bindings used by the Debian package.

## License

No license is asserted by this repository yet. Before publishing publicly, choose and add the license that matches how you want others to use and distribute the project.
