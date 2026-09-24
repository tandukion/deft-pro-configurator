import copy
import json
import os
import tempfile
from pathlib import Path

APP_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "deft-pro"
CONFIG_FILE = APP_DIR / "config.json"
SOCKET_FILE = APP_DIR / "daemon.sock"
STATE_FILE = APP_DIR / "state.json"

BUTTONS = [
    (1, "Left click"), (2, "Middle click"), (3, "Right click"),
    (4, "Wheel up"), (5, "Wheel down"), (6, "Wheel tilt left"),
    (7, "Wheel tilt right"), (8, "Back"), (9, "Forward"),
    (10, "Fn1"), (11, "Fn2"), (12, "Fn3"),
]
BUTTON_NAMES = dict(BUTTONS)

DEFAULT_CONFIG = {
    "version": 1,
    "device_hint": "DEFT Pro TrackBall",
    "profiles": {
        "Default": {
            "bindings": {str(i): {"type": "passthrough"} for i, _ in BUTTONS}
        }
    },
    "active_profile": "Default",
}

KEY_NAMES = [
    "ESC", "TAB", "CAPSLOCK", "SHIFT", "CTRL", "ALT", "SUPER", "META",
    "ENTER", "SPACE", "BACKSPACE", "DELETE", "INSERT", "HOME", "END",
    "PAGEUP", "PAGEDOWN", "UP", "DOWN", "LEFT", "RIGHT", "PRINTSCREEN",
    "PAUSE", "MENU", "NUMLOCK", "SCROLLLOCK", "F1", "F2", "F3", "F4",
    "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "A", "B", "C",
    "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P",
    "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "0", "1", "2",
    "3", "4", "5", "6", "7", "8", "9", "MINUS", "EQUAL", "LEFTBRACE",
    "RIGHTBRACE", "BACKSLASH", "SEMICOLON", "APOSTROPHE", "GRAVE", "COMMA",
    "DOT", "SLASH",
]

ACTION_LABELS = {
    "passthrough": "Pass through",
    "disabled": "Disabled",
    "mouse_button": "Mouse button",
    "key": "Keyboard key",
    "hotkey": "Keyboard shortcut",
    "command": "Launch command",
    "scroll": "Scroll",
}


def fresh_config():
    return copy.deepcopy(DEFAULT_CONFIG)


def ensure_config():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        atomic_write(CONFIG_FILE, DEFAULT_CONFIG)


def atomic_write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def load_config():
    ensure_config()
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = fresh_config()
    data.setdefault("version", 1)
    data.setdefault("device_hint", "DEFT Pro TrackBall")
    data.setdefault("profiles", {})
    if not data["profiles"]:
        data["profiles"] = fresh_config()["profiles"]
    data.setdefault("active_profile", next(iter(data["profiles"])))
    if data["active_profile"] not in data["profiles"]:
        data["active_profile"] = next(iter(data["profiles"]))
    for profile in data["profiles"].values():
        bindings = profile.setdefault("bindings", {})
        for n, _ in BUTTONS:
            bindings.setdefault(str(n), {"type": "passthrough"})
    return data
