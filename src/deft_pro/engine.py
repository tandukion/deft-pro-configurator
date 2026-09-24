import json
import os
import queue
import socket
import subprocess
import threading
import time
from pathlib import Path

try:
    import evdev
    from evdev import InputDevice, UInput, ecodes as e
except ImportError as exc:  # pragma: no cover - dependency handled by .deb
    evdev = None
    e = None
    InputDevice = None
    UInput = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

from .config import CONFIG_FILE, SOCKET_FILE, STATE_FILE, load_config


class Remapper:
    def __init__(self):
        if IMPORT_ERROR:
            raise RuntimeError(f"python3-evdev is required: {IMPORT_ERROR}")
        self.stop_event = threading.Event()
        self.device = None
        self.ui = None
        self.thread = None
        self.server_thread = None
        self.learn_lock = threading.Lock()
        self.learn_queue = queue.Queue()
        self.status_lock = threading.Lock()
        self.status = {"running": False, "device": None, "message": "Starting…", "last_button": None}
        self.config = load_config()
        self.config_mtime = 0
        self.active_outputs = {}
        self.active_profile = self.config.get("active_profile", "Default")
        self.release_all = False

    def update_status(self, **kwargs):
        with self.status_lock:
            self.status.update(kwargs)
            payload = dict(self.status)
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass

    def find_device(self):
        hint = self.config.get("device_hint", "DEFT Pro TrackBall").lower()
        candidates = []
        for path in evdev.list_devices():
            try:
                dev = InputDevice(path)
                name = (dev.name or "").lower()
                caps = dev.capabilities()
                buttons = set(caps.get(e.EV_KEY, []))
                if e.BTN_LEFT not in buttons and e.BTN_RIGHT not in buttons:
                    dev.close()
                    continue
                score = 0
                if "deft pro" in name:
                    score += 100
                if "trackball" in name:
                    score += 30
                if hint and hint in name:
                    score += 20
                score += min(20, len(buttons))
                candidates.append((score, dev))
            except OSError:
                continue
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def create_uinput(self, dev):
        caps = dev.capabilities(absinfo=True)
        events = {
            e.EV_KEY: [x for x in caps.get(e.EV_KEY, []) if x >= e.BTN_LEFT],
            e.EV_REL: caps.get(e.EV_REL, []),
        }
        # Ensure all standard buttons, plus wheel/side buttons, exist on the virtual pointer.
        btns = set(events[e.EV_KEY])
        btns.update([e.BTN_LEFT, e.BTN_MIDDLE, e.BTN_RIGHT, e.BTN_SIDE, e.BTN_EXTRA,
                     e.BTN_FORWARD, e.BTN_BACK, e.BTN_TASK])
        for n in range(1, 13):
            code = e.BTN_MOUSE + n - 1
            btns.add(code)
        events[e.EV_KEY] = sorted(btns)
        rels = list(events.get(e.EV_REL, []))
        for code in (e.REL_X, e.REL_Y, e.REL_WHEEL, e.REL_HWHEEL):
            if code not in rels:
                rels.append(code)
        events[e.EV_REL] = rels
        return UInput(events, name="DEFT Pro Configurator Virtual Trackball", version=1)

    def release_active(self):
        if not self.ui:
            return
        for state in self.active_outputs.values():
            try:
                if isinstance(state, tuple) and len(state) == 2 and isinstance(state[0], list):
                    mods, key = state
                    self.ui.write(e.EV_KEY, key, 0)
                    for mod in reversed(mods):
                        self.ui.write(e.EV_KEY, mod, 0)
                else:
                    self.ui.write(e.EV_KEY, int(state), 0)
            except (OSError, TypeError, ValueError):
                pass
        self.active_outputs.clear()
        try:
            self.ui.syn()
        except OSError:
            pass

    def profile(self):
        profiles = self.config.get("profiles", {})
        return profiles.get(self.active_profile) or next(iter(profiles.values()))

    def binding_for(self, source_button):
        return self.profile().get("bindings", {}).get(str(source_button), {"type": "passthrough"})

    def emit_key(self, code, value):
        self.ui.write(e.EV_KEY, code, value)

    # DEFT Pro logical button numbering as exposed by X11/libinput, mapped to
    # the Linux evdev button codes emitted by the physical device.
    LOGICAL_TO_EVDEV = {
        1: e.BTN_LEFT,
        2: e.BTN_MIDDLE,
        3: e.BTN_RIGHT,
        8: e.BTN_SIDE,
        9: e.BTN_EXTRA,
        10: e.BTN_FORWARD,
        11: e.BTN_BACK,
        12: e.BTN_TASK,
    }
    EVDEV_TO_LOGICAL = {v: k for k, v in LOGICAL_TO_EVDEV.items()}

    def emit_button(self, button_num, value):
        code = self.LOGICAL_TO_EVDEV.get(int(button_num))
        if code is not None:
            self.emit_key(code, value)

    def key_code(self, name):
        name = (name or "").upper()
        alias = {
            "CTRL": "KEY_LEFTCTRL", "CONTROL": "KEY_LEFTCTRL", "ALT": "KEY_LEFTALT",
            "SHIFT": "KEY_LEFTSHIFT", "SUPER": "KEY_LEFTMETA", "META": "KEY_LEFTMETA",
            "ENTER": "KEY_ENTER", "ESC": "KEY_ESC", "TAB": "KEY_TAB", "SPACE": "KEY_SPACE",
            "BACKSPACE": "KEY_BACKSPACE", "DELETE": "KEY_DELETE", "INSERT": "KEY_INSERT",
            "UP": "KEY_UP", "DOWN": "KEY_DOWN", "LEFT": "KEY_LEFT", "RIGHT": "KEY_RIGHT",
            "HOME": "KEY_HOME", "END": "KEY_END", "PAGEUP": "KEY_PAGEUP", "PAGEDOWN": "KEY_PAGEDOWN",
            "PRINTSCREEN": "KEY_SYSRQ", "NUMLOCK": "KEY_NUMLOCK", "SCROLLLOCK": "KEY_SCROLLLOCK",
            "MINUS": "KEY_MINUS", "EQUAL": "KEY_EQUAL", "LEFTBRACE": "KEY_LEFTBRACE", "RIGHTBRACE": "KEY_RIGHTBRACE",
            "BACKSLASH": "KEY_BACKSLASH", "SEMICOLON": "KEY_SEMICOLON", "APOSTROPHE": "KEY_APOSTROPHE",
            "GRAVE": "KEY_GRAVE", "COMMA": "KEY_COMMA", "DOT": "KEY_DOT", "SLASH": "KEY_SLASH",
        }
        if name in alias:
            return getattr(e, alias[name])
        if len(name) == 1 and name.isalpha():
            return getattr(e, "KEY_" + name)
        if len(name) == 1 and name.isdigit():
            return getattr(e, "KEY_" + name)
        if name.startswith("F") and name[1:].isdigit():
            n = int(name[1:])
            if 1 <= n <= 24:
                return getattr(e, f"KEY_F{n}")
        const = name if name.startswith("KEY_") else "KEY_" + name
        return getattr(e, const, None)

    def do_binding(self, source, binding, down):
        typ = binding.get("type", "passthrough")
        if typ == "passthrough":
            self.emit_button(source, 1 if down else 0)
            return
        if typ == "disabled":
            return
        if typ == "mouse_button":
            target = int(binding.get("button", 1))
            self.emit_button(target, 1 if down else 0)
            self.active_outputs[source] = target
            return
        if typ == "key":
            code = self.key_code(binding.get("key"))
            if code is not None:
                self.emit_key(code, 1 if down else 0)
                if down:
                    self.active_outputs[source] = code
                else:
                    self.active_outputs.pop(source, None)
            return
        if typ == "hotkey":
            mods = [self.key_code(x) for x in binding.get("mods", [])]
            key = self.key_code(binding.get("key"))
            mods = [x for x in mods if x is not None]
            if key is None:
                return
            if down:
                for mod in mods:
                    self.emit_key(mod, 1)
                self.emit_key(key, 1)
                self.active_outputs[source] = (mods, key)
            else:
                state = self.active_outputs.pop(source, (mods, key))
                mods2, key2 = state if isinstance(state, tuple) else (mods, key)
                self.emit_key(key2, 0)
                for mod in reversed(mods2):
                    self.emit_key(mod, 0)
            return
        if typ == "command":
            if down:
                cmd = binding.get("command", "").strip()
                if cmd:
                    try:
                        subprocess.Popen(cmd, shell=True, start_new_session=True)
                    except OSError:
                        pass
            return
        if typ == "scroll":
            if down:
                axis = binding.get("axis", "vertical")
                amount = int(binding.get("amount", 1))
                code = e.REL_HWHEEL if axis == "horizontal" else e.REL_WHEEL
                self.ui.write(e.EV_REL, code, amount)
            return
        self.emit_button(source, 1 if down else 0)

    def do_pulse_binding(self, source, binding):
        """Apply a momentary action for wheel/tilt inputs."""
        typ = binding.get("type", "passthrough")
        if typ == "passthrough":
            return False
        if typ == "disabled":
            return True
        if typ == "mouse_button":
            target = int(binding.get("button", 1))
            self.emit_button(target, 1)
            self.emit_button(target, 0)
            return True
        if typ == "key":
            code = self.key_code(binding.get("key"))
            if code is not None:
                self.emit_key(code, 1)
                self.emit_key(code, 0)
            return True
        if typ == "hotkey":
            mods = [self.key_code(x) for x in binding.get("mods", [])]
            key = self.key_code(binding.get("key"))
            mods = [x for x in mods if x is not None]
            if key is not None:
                for mod in mods:
                    self.emit_key(mod, 1)
                self.emit_key(key, 1)
                self.emit_key(key, 0)
                for mod in reversed(mods):
                    self.emit_key(mod, 0)
            return True
        if typ == "command":
            cmd = binding.get("command", "").strip()
            if cmd:
                try:
                    subprocess.Popen(cmd, shell=True, start_new_session=True)
                except OSError:
                    pass
            return True
        if typ == "scroll":
            axis = binding.get("axis", "vertical")
            amount = int(binding.get("amount", 1))
            code = e.REL_HWHEEL if axis == "horizontal" else e.REL_WHEEL
            self.ui.write(e.EV_REL, code, amount)
            return True
        return True

    def handle_event(self, event):
        # Wheel/tilt are EV_REL rather than EV_KEY on Linux. The DEFT Pro/X11
        # logical numbering is B4=wheel up, B5=wheel down, B6=tilt left,
        # B7=tilt right. Positive REL_WHEEL is up; positive REL_HWHEEL is right.
        if event.type == e.EV_REL and event.code in (e.REL_WHEEL, e.REL_HWHEEL):
            if event.value == 0:
                return
            if event.code == e.REL_WHEEL:
                source = 4 if event.value > 0 else 5
            else:
                source = 7 if event.value > 0 else 6
            binding = self.binding_for(source)
            if binding.get("type", "passthrough") == "passthrough":
                self.ui.write(event.type, event.code, event.value)
            else:
                self.update_status(last_button=source)
                self.do_pulse_binding(source, binding)
            try:
                while True:
                    self.learn_queue.get_nowait()
                    self.learn_result = source
            except queue.Empty:
                pass
            return
        if event.type == e.EV_REL:
            self.ui.write(event.type, event.code, event.value)
            return
        if event.type != e.EV_KEY:
            return
        source = self.EVDEV_TO_LOGICAL.get(event.code)
        if source is None:
            return
        value = event.value
        if value == 1:
            down = True
        elif value == 0:
            down = False
        elif value == 2:
            down = True
        else:
            return
        self.update_status(last_button=source)
        try:
            while True:
                self.learn_queue.get_nowait()
                self.learn_result = source
        except queue.Empty:
            pass
        self.do_binding(source, self.binding_for(source), down)

    def server(self):
        SOCKET_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            SOCKET_FILE.unlink()
        except FileNotFoundError:
            pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(SOCKET_FILE))
        os.chmod(SOCKET_FILE, 0o600)
        srv.listen(4)
        srv.settimeout(0.5)
        while not self.stop_event.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                try:
                    data = conn.recv(4096).decode("utf-8")
                    req = json.loads(data or "{}")
                    cmd = req.get("cmd")
                    if cmd == "status":
                        with self.status_lock:
                            out = dict(self.status)
                        conn.sendall(json.dumps(out).encode())
                    elif cmd == "learn":
                        self.learn_result = None
                        self.learn_queue.put(True)
                        deadline = time.time() + 10
                        while time.time() < deadline and not self.stop_event.is_set():
                            if getattr(self, "learn_result", None):
                                result = {"ok": True, "button": self.learn_result}
                                self.learn_result = None
                                break
                            time.sleep(0.03)
                        else:
                            result = {"ok": False, "error": "Timed out waiting for a button press"}
                        conn.sendall(json.dumps(result).encode())
                    elif cmd == "reload":
                        self.reload_config(force=True)
                        conn.sendall(b'{"ok":true}')
                    elif cmd == "stop":
                        self.stop_event.set()
                        conn.sendall(b'{"ok":true}')
                    else:
                        conn.sendall(b'{"ok":false,"error":"unknown command"}')
                except Exception as exc:
                    try:
                        conn.sendall(json.dumps({"ok": False, "error": str(exc)}).encode())
                    except OSError:
                        pass
        try:
            srv.close()
        finally:
            try:
                SOCKET_FILE.unlink()
            except FileNotFoundError:
                pass

    def reload_config(self, force=False):
        try:
            mtime = CONFIG_FILE.stat().st_mtime_ns
        except OSError:
            mtime = 0
        if force or mtime != self.config_mtime:
            self.release_active()
            self.config = load_config()
            self.active_profile = self.config.get("active_profile", "Default")
            self.config_mtime = mtime
            self.update_status(message=f"Profile: {self.active_profile}")

    def run(self):
        self.reload_config(force=True)
        self.server_thread = threading.Thread(target=self.server, daemon=True)
        self.server_thread.start()
        while not self.stop_event.is_set():
            self.reload_config()
            dev = self.find_device()
            if dev is None:
                self.update_status(running=False, device=None, message="DEFT Pro not detected — connect it")
                time.sleep(2)
                continue
            try:
                self.update_status(running=False, device=dev.name, message="Connecting…")
                dev.grab()
                self.device = dev
                self.ui = self.create_uinput(dev)
                self.ui.sleep_interval = 0.0
                self.update_status(running=True, device=dev.name, message=f"Active — {self.active_profile}")
                for event in dev.read_loop():
                    if self.stop_event.is_set():
                        break
                    self.reload_config()
                    self.handle_event(event)
                    try:
                        self.ui.syn()
                    except OSError:
                        break
            except (OSError, PermissionError) as exc:
                self.update_status(running=False, device=getattr(dev, "name", None), message=f"Device error: {exc}")
                time.sleep(1)
            finally:
                self.release_active()
                if self.ui:
                    try:
                        self.ui.close()
                    except OSError:
                        pass
                    self.ui = None
                try:
                    dev.ungrab()
                except Exception:
                    pass
                try:
                    dev.close()
                except Exception:
                    pass
                self.device = None
        self.update_status(running=False, device=None, message="Stopped")


def run_daemon():
    Remapper().run()
