import json
import os
import socket
import subprocess
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from .config import ACTION_LABELS, BUTTON_NAMES, BUTTONS, CONFIG_FILE, load_config, atomic_write, APP_DIR


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.deftpro.configurator")
        self.window = None
        self.config = load_config()
        self.selected = 10
        self.action_type = None
        self.form_widgets = {}
        self.status_label = None
        self.device_label = None
        self.profile_combo = None
        self.grid_buttons = {}
        self.load_profile()

    def do_activate(self):
        if self.window is None:
            self.build_ui()
        self.window.present()
        self.ensure_daemon()
        self.refresh_status()

    def ensure_daemon(self):
        try:
            out = subprocess.run(["systemctl", "--user", "is-active", "deft-pro-daemon.service"], capture_output=True, text=True, timeout=2)
            if out.stdout.strip() != "active":
                subprocess.run(["systemctl", "--user", "start", "deft-pro-daemon.service"], check=False, timeout=3)
        except Exception:
            pass

    def build_ui(self):
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("DEFT Pro Configurator")
        self.window.set_default_size(980, 660)
        self.window.set_border_width(12)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.window.add(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        root.pack_start(header, False, False, 0)
        title = Gtk.Label()
        title.set_markup("<big><b>DEFT Pro Configurator</b></big>")
        title.set_xalign(0)
        header.pack_start(title, True, True, 0)
        self.device_label = Gtk.Label(label="Checking device…")
        self.device_label.set_xalign(1)
        header.pack_end(self.device_label, False, False, 0)

        paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        root.pack_start(paned, True, True, 0)
        paned.set_position(430)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        paned.add1(left)
        info = Gtk.Label(label="Select a physical button, then assign an action.")
        info.set_xalign(0)
        left.pack_start(info, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        left.pack_start(scrolled, True, True, 0)
        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_border_width(6)
        scrolled.add(grid)

        for idx, (num, name) in enumerate(BUTTONS):
            b = Gtk.Button()
            b.set_hexpand(True)
            b.set_vexpand(False)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            n = Gtk.Label(label=f"B{num}")
            n.set_markup(f"<b>B{num}</b>")
            d = Gtk.Label(label=name)
            box.pack_start(n, False, False, 0)
            box.pack_start(d, False, False, 0)
            b.add(box)
            b.connect("clicked", self.select_button, num)
            row, col = divmod(idx, 3)
            grid.attach(b, col, row, 1, 1)
            self.grid_buttons[num] = b

        preset_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        left.pack_start(preset_row, False, False, 0)
        preset = Gtk.Button(label="Apply common ergonomic preset")
        preset.connect("clicked", self.apply_preset)
        preset_row.pack_start(preset, False, False, 0)
        reset = Gtk.Button(label="Reset selected")
        reset.connect("clicked", self.reset_selected)
        preset_row.pack_end(reset, False, False, 0)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        paned.add2(right)

        selected_label = Gtk.Label()
        selected_label.set_xalign(0)
        selected_label.set_markup("<big><b>Button</b></big>")
        self.selected_label = selected_label
        right.pack_start(selected_label, False, False, 0)

        form = Gtk.Grid(column_spacing=10, row_spacing=10)
        right.pack_start(form, False, False, 0)

        form.attach(Gtk.Label(label="Action:", xalign=0), 0, 0, 1, 1)
        self.type_combo = Gtk.ComboBoxText()
        for typ, label in ACTION_LABELS.items():
            self.type_combo.append(typ, label)
        self.type_combo.connect("changed", self.type_changed)
        form.attach(self.type_combo, 1, 0, 2, 1)

        self.dynamic_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right.pack_start(self.dynamic_box, False, False, 0)

        profile_frame = Gtk.Frame(label="Profile")
        profile_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        profile_box.set_border_width(8)
        profile_frame.add(profile_box)
        self.profile_combo = Gtk.ComboBoxText()
        self.profile_combo.connect("changed", self.profile_changed)
        profile_box.pack_start(self.profile_combo, True, True, 0)
        for label, handler in (("New", self.new_profile), ("Duplicate", self.duplicate_profile), ("Delete", self.delete_profile)):
            bb = Gtk.Button(label=label)
            bb.connect("clicked", handler)
            profile_box.pack_start(bb, False, False, 0)
        right.pack_start(profile_frame, False, False, 0)

        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        right.pack_end(action_row, False, False, 0)
        apply_b = Gtk.Button(label="Apply changes")
        apply_b.connect("clicked", self.apply_binding)
        action_row.pack_end(apply_b, False, False, 0)
        learn_b = Gtk.Button(label="Learn physical button…")
        learn_b.connect("clicked", self.learn)
        action_row.pack_start(learn_b, False, False, 0)

        self.status_label = Gtk.Label(label="")
        self.status_label.set_xalign(0)
        root.pack_end(self.status_label, False, False, 0)

        self.populate_profiles()
        self.select_button(None, 10)

        self.window.show_all()

    def populate_profiles(self):
        self.profile_combo.remove_all()
        for name in self.config["profiles"]:
            self.profile_combo.append(name, name)
        self.profile_combo.set_active_id(self.config.get("active_profile", "Default"))

    def load_profile(self):
        self.profile = self.config["profiles"][self.config["active_profile"]]

    def profile_changed(self, combo):
        name = combo.get_active_id()
        if not name or name == self.config.get("active_profile"):
            return
        self.save_current_from_form()
        self.config["active_profile"] = name
        self.load_profile()
        self.select_button(None, self.selected)
        self.persist()

    def new_profile(self, _):
        idx = 1
        while f"Profile {idx}" in self.config["profiles"]:
            idx += 1
        self.save_current_from_form()
        self.config["profiles"][f"Profile {idx}"] = json.loads(json.dumps(self.profile))
        self.config["active_profile"] = f"Profile {idx}"
        self.load_profile()
        self.populate_profiles()
        self.persist()

    def duplicate_profile(self, _):
        src = self.config.get("active_profile", "Default")
        idx = 1
        while f"{src} Copy {idx}" in self.config["profiles"]:
            idx += 1
        self.save_current_from_form()
        name = f"{src} Copy {idx}"
        self.config["profiles"][name] = json.loads(json.dumps(self.profile))
        self.config["active_profile"] = name
        self.load_profile()
        self.populate_profiles()
        self.persist()

    def delete_profile(self, _):
        if len(self.config["profiles"]) <= 1:
            self.set_status("Keep at least one profile.")
            return
        old = self.config["active_profile"]
        del self.config["profiles"][old]
        self.config["active_profile"] = next(iter(self.config["profiles"]))
        self.load_profile()
        self.populate_profiles()
        self.select_button(None, self.selected)
        self.persist()

    def make_entry(self, text=""):
        w = Gtk.Entry()
        w.set_text(text)
        return w

    def clear_dynamic(self):
        for child in self.dynamic_box.get_children():
            self.dynamic_box.remove(child)
        self.form_widgets = {}

    def select_button(self, _, num):
        self.save_current_from_form()
        self.selected = num
        self.selected_label.set_markup(f"<big><b>B{num} — {BUTTON_NAMES[num]}</b></big>")
        binding = self.profile["bindings"].get(str(num), {"type": "passthrough"})
        typ = binding.get("type", "passthrough")
        self.type_combo.set_active_id(typ)
        self.render_form(binding)
        for n, b in self.grid_buttons.items():
            b.get_style_context().remove_class("suggested-action")
        self.grid_buttons[num].get_style_context().add_class("suggested-action")

    def type_changed(self, combo):
        typ = combo.get_active_id()
        if typ:
            self.render_form(self.profile["bindings"].get(str(self.selected), {"type": typ}) if typ == self.profile["bindings"].get(str(self.selected), {}).get("type") else {"type": typ})

    def render_form(self, binding):
        self.clear_dynamic()
        typ = binding.get("type", "passthrough")
        if typ in ("passthrough", "disabled"):
            text = "The original button event will be forwarded." if typ == "passthrough" else "This button will do nothing."
            self.dynamic_box.pack_start(Gtk.Label(label=text, xalign=0), False, False, 0)
        elif typ == "mouse_button":
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.pack_start(Gtk.Label(label="Mouse button:"), False, False, 0)
            combo = Gtk.ComboBoxText()
            target_buttons = [1, 2, 3, 8, 9, 10, 11, 12]
            for n in target_buttons:
                combo.append(str(n), f"Button {n} — {BUTTON_NAMES.get(n, 'Extra')}")
            combo.set_active_id(str(binding.get("button", 1)))
            row.pack_start(combo, True, True, 0)
            self.form_widgets["button"] = combo
            self.dynamic_box.pack_start(row, False, False, 0)
        elif typ == "key":
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.pack_start(Gtk.Label(label="Key:"), False, False, 0)
            entry = self.make_entry(binding.get("key", ""))
            entry.set_placeholder_text("e.g. F5, A, ENTER, SPACE")
            row.pack_start(entry, True, True, 0)
            self.form_widgets["key"] = entry
            self.dynamic_box.pack_start(row, False, False, 0)
        elif typ == "hotkey":
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            key = self.make_entry(binding.get("key", ""))
            key.set_placeholder_text("Key, e.g. S")
            mods = self.make_entry("+".join(binding.get("mods", [])))
            mods.set_placeholder_text("Modifiers, e.g. CTRL+SHIFT")
            row.pack_start(Gtk.Label(label="Modifiers (separate with +):", xalign=0), False, False, 0)
            row.pack_start(mods, False, False, 0)
            row.pack_start(Gtk.Label(label="Key:", xalign=0), False, False, 0)
            row.pack_start(key, False, False, 0)
            self.form_widgets.update({"mods": mods, "key": key})
            self.dynamic_box.pack_start(row, False, False, 0)
        elif typ == "command":
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            entry = self.make_entry(binding.get("command", ""))
            entry.set_placeholder_text("e.g. gnome-terminal")
            row.pack_start(Gtk.Label(label="Shell command:", xalign=0), False, False, 0)
            row.pack_start(entry, False, False, 0)
            self.form_widgets["command"] = entry
            self.dynamic_box.pack_start(row, False, False, 0)
        elif typ == "scroll":
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            axis = Gtk.ComboBoxText(); axis.append("vertical", "Vertical"); axis.append("horizontal", "Horizontal"); axis.set_active_id(binding.get("axis", "vertical"))
            amt = self.make_entry(str(binding.get("amount", 1)))
            row.pack_start(Gtk.Label(label="Axis:"), False, False, 0); row.pack_start(axis, True, True, 0)
            row.pack_start(Gtk.Label(label="Amount:"), False, False, 0); row.pack_start(amt, False, False, 0)
            self.form_widgets.update({"axis": axis, "amount": amt})
            self.dynamic_box.pack_start(row, False, False, 0)
        self.dynamic_box.show_all()

    def current_form_binding(self):
        typ = self.type_combo.get_active_id() or "passthrough"
        if typ in ("passthrough", "disabled"):
            return {"type": typ}
        if typ == "mouse_button":
            return {"type": typ, "button": int(self.form_widgets["button"].get_active_id() or 1)}
        if typ == "key":
            return {"type": typ, "key": self.form_widgets["key"].get_text().strip().upper()}
        if typ == "hotkey":
            mods = [x.strip().upper() for x in self.form_widgets["mods"].get_text().split("+") if x.strip()]
            return {"type": typ, "mods": mods, "key": self.form_widgets["key"].get_text().strip().upper()}
        if typ == "command":
            return {"type": typ, "command": self.form_widgets["command"].get_text()}
        if typ == "scroll":
            try: amount = int(self.form_widgets["amount"].get_text())
            except ValueError: amount = 1
            return {"type": typ, "axis": self.form_widgets["axis"].get_active_id() or "vertical", "amount": amount}
        return {"type": "passthrough"}

    def save_current_from_form(self):
        if not self.type_combo or not self.profile:
            return
        self.profile["bindings"][str(self.selected)] = self.current_form_binding()

    def apply_binding(self, _):
        self.save_current_from_form()
        self.persist()
        self.set_status(f"Saved B{self.selected} in profile '{self.config['active_profile']}'.")

    def reset_selected(self, _):
        self.profile["bindings"][str(self.selected)] = {"type": "passthrough"}
        self.select_button(None, self.selected)
        self.persist()

    def apply_preset(self, _):
        # Common DEFT Pro ergonomic preset: Fn1 = left, Fn2 = middle, Fn3 = right.
        self.profile["bindings"].update({"10": {"type": "mouse_button", "button": 1}, "11": {"type": "mouse_button", "button": 2}, "12": {"type": "mouse_button", "button": 3}})
        self.select_button(None, self.selected)
        self.persist()
        self.set_status("Applied Fn1→left, Fn2→middle, Fn3→right.")

    def persist(self):
        self.config["profiles"][self.config["active_profile"]] = self.profile
        atomic_write(CONFIG_FILE, self.config)
        try:
            self.send_daemon({"cmd": "reload"})
        except Exception:
            pass

    def send_daemon(self, payload):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(str(APP_DIR / "daemon.sock"))
        s.sendall(json.dumps(payload).encode())
        data = s.recv(4096)
        s.close()
        return json.loads(data.decode() or "{}")

    def learn(self, _):
        dialog = Gtk.MessageDialog(transient_for=self.window, flags=0, message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.CANCEL, text="Press a DEFT Pro button")
        dialog.format_secondary_text("The next DEFT Pro button press will select that button.")
        dialog.show_all()
        def worker():
            try:
                result = self.send_daemon({"cmd": "learn"})
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}
            GLib.idle_add(done, result)
        def done(result):
            dialog.destroy()
            if result.get("ok"):
                self.select_button(None, int(result["button"]))
                self.set_status(f"Detected physical button B{result['button']}.")
            else:
                self.set_status("Learn failed: " + result.get("error", "unknown error"))
            return False
        threading.Thread(target=worker, daemon=True).start()

    def refresh_status(self):
        def worker():
            try:
                result = self.send_daemon({"cmd": "status"})
            except Exception as exc:
                result = {"running": False, "device": None, "message": str(exc)}
            GLib.idle_add(update, result)
        def update(result):
            running = result.get("running")
            device = result.get("device")
            message = result.get("message", "")
            self.device_label.set_text(("● Connected: " + device) if running and device else "○ " + (message or "Not connected"))
            self.status_label.set_text(message)
            return False
        threading.Thread(target=worker, daemon=True).start()
        GLib.timeout_add(1500, self.refresh_status)
        return False

    def set_status(self, msg):
        if self.status_label:
            self.status_label.set_text(msg)


def run_gui():
    app = App()
    return app.run(None)
