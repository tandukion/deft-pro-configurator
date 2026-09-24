# Configuration reference

DEFT Pro Configurator keeps its user configuration in:

```text
~/.config/deft-pro/config.json
```

A minimal configuration looks like:

```json
{
  "version": 1,
  "device_hint": "DEFT Pro TrackBall",
  "active_profile": "Default",
  "profiles": {
    "Default": {
      "bindings": {
        "1": {"type": "passthrough"},
        "2": {"type": "passthrough"},
        "3": {"type": "passthrough"},
        "4": {"type": "passthrough"},
        "5": {"type": "passthrough"},
        "6": {"type": "passthrough"},
        "7": {"type": "passthrough"},
        "8": {"type": "passthrough"},
        "9": {"type": "passthrough"},
        "10": {"type": "passthrough"},
        "11": {"type": "passthrough"},
        "12": {"type": "passthrough"}
      }
    }
  }
}
```

## Logical button numbers

The application uses these logical names:

| Number | Meaning |
|---:|---|
| B1 | Left click |
| B2 | Middle click |
| B3 | Right click |
| B4 | Wheel up |
| B5 | Wheel down |
| B6 | Wheel tilt left |
| B7 | Wheel tilt right |
| B8 | Back |
| B9 | Forward |
| B10 | Fn1 |
| B11 | Fn2 |
| B12 | Fn3 |

Use **Learn physical button…** in the GUI to verify how a particular device exposes its events.

## Action types

### `passthrough`

Forward the original logical button event.

```json
{"type": "passthrough"}
```

### `disabled`

Ignore the input.

```json
{"type": "disabled"}
```

### `mouse_button`

Emit another mouse button.

```json
{"type": "mouse_button", "button": 3}
```

### `key`

Emit a keyboard key.

```json
{"type": "key", "key": "F5"}
```

### `hotkey`

Emit one key plus zero or more modifiers.

```json
{
  "type": "hotkey",
  "mods": ["CTRL", "SHIFT"],
  "key": "S"
}
```

### `command`

Launch a shell command when the input is activated.

```json
{"type": "command", "command": "gnome-terminal"}
```

Treat this as executable configuration; the command runs as the desktop user.

### `scroll`

Emit a scroll event.

```json
{
  "type": "scroll",
  "axis": "vertical",
  "amount": 1
}
```

For horizontal scrolling, use `"axis": "horizontal"`.

## Configuration paths

| Path | Purpose |
|---|---|
| `~/.config/deft-pro/config.json` | Persistent profiles and bindings |
| `~/.config/deft-pro/state.json` | Current daemon status |
| `~/.config/deft-pro/daemon.sock` | Local GUI/daemon control socket |

## Editing JSON manually

Manual editing is supported, but the GUI is preferred because it validates/normalizes common values and automatically reloads the daemon after saving.

If you edit the JSON while the daemon is running, the daemon checks the modification time and reloads the configuration.

Keep a backup before making large manual changes:

```bash
cp ~/.config/deft-pro/config.json ~/.config/deft-pro/config.json.bak
```
