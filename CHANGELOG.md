# Changelog

All notable changes to DEFT Pro Configurator are documented here.

## [1.0.2] - 2026-09-24

### Fixed
- Fixed Bluetooth DEFT Pro permissions when the device is already connected during installation or upgrade.
- Removed the `ACTION=="add"` restriction from the DEFT Pro udev rule so `udevadm trigger` can apply the rule to existing devices.
- Added a Bluetooth mouse-class check while retaining the `DEFT Pro` device-name match.
- Package installation now reloads udev rules and refreshes the current user's daemon when possible.
- Added a regression test for the udev-rule behavior.

### Verified
- DEFT Pro Bluetooth device is exposed on Linux as `DEFT Pro TrackBall`.
- The daemon successfully reports `Active — Default` after access is granted.

## [1.0.1]

### Fixed
- Improved Bluetooth device-name detection and permission diagnostics.
- Added Bluetooth-specific udev matching.

## [1.0.0]

### Added
- Initial GTK GUI configurator and evdev/uinput remapper.
- Profiles, button learning, keyboard shortcuts, shell commands, and autostart.
