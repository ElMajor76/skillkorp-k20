#!/usr/bin/env python3
"""
SkillKorp K20 Ultimate - System Tray Indicator & Notifications
Supports:
- Real-time battery level in tray icon & menu
- Low battery alerts & charging notifications via desktop notifications
- Instant RGB lighting effect switching from tray menu
- Instant Polling rate switching (125 Hz - 1000 Hz)
- Windows Key Lock toggle
- Multi-profile switching from tray menu
- Automatic profile switching based on active application
- Autostart toggle
"""

import os
import sys
import subprocess
import time
from typing import Optional, Dict, List

# Add project directory to python path
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, BASE_DIR)

import gi
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as appindicator
except Exception:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as appindicator

from gi.repository import Gtk, GLib
try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify
    HAS_NOTIFY = True
except Exception:
    HAS_NOTIFY = False

from k20_driver import (
    SkillkorpK20Driver,
    LIGHT_MODES,
    POLLING_RATE_MAP,
)
from profile_manager import (
    ProfileManager,
    detect_active_window_class,
    is_autostart_enabled,
    set_autostart,
)


class K20TrayApp:
    def __init__(self):
        self.driver = SkillkorpK20Driver()
        self.pm = ProfileManager()
        if HAS_NOTIFY:
            Notify.init("SkillKorp K20")

        self.last_battery: Optional[int] = None
        self.last_charging: Optional[bool] = None
        self.last_connected: Optional[bool] = None
        self.last_active_window: Optional[str] = None
        self.last_profile_id: str = self.pm.get_active_profile_id()
        self.warned_low_20 = False
        self.warned_low_10 = False

        # Build AppIndicator
        self.indicator = appindicator.Indicator.new(
            "skillkorp-k20-tray",
            "skillkorp-k20",
            appindicator.IndicatorCategory.HARDWARE,
        )
        self.indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title("SkillKorp K20 Ultimate")

        # Custom icon path if exists
        icon_path = os.path.join(BASE_DIR, "assets", "skillkorp-k20.png")
        if os.path.exists(icon_path):
            self.indicator.set_icon_full(icon_path, "SkillKorp K20")

        self.menu = Gtk.Menu()
        self._build_menu()
        self.indicator.set_menu(self.menu)

        # Initial check
        self._update_status()

        # Update timers
        GLib.timeout_add_seconds(4, self._on_status_timer)
        GLib.timeout_add(1000, self._on_auto_switch_timer)

    def _notify(self, title: str, body: str, urgency: int = 1):
        if not HAS_NOTIFY:
            return
        try:
            n = Notify.Notification.new(title, body, "skillkorp-k20")
            n.set_urgency(urgency)
            n.set_timeout(3000)
            n.show()
        except Exception:
            pass

    def _get_battery_icon_name(self, pct: int, charging: bool) -> str:
        if charging:
            return "battery-level-100-charged-symbolic"
        step = min(100, max(0, (pct // 10) * 10))
        return f"battery-level-{step}-symbolic"

    def _update_status(self):
        self.driver.reload_config_if_changed()
        connected = self.driver.is_connected()
        bat = self.driver.get_battery()
        pct = bat.get("percentage") or 0
        charging = bat.get("charging", False)

        # Notifications for connection changes
        if self.last_connected is not None and self.last_connected != connected:
            if connected:
                mode_str = "sans-fil 2.4GHz" if self.driver.is_wireless() else "filaire USB"
                self._notify("Clavier connecté", f"SkillKorp K20 détecté en mode {mode_str}.")
            else:
                self._notify("Clavier déconnecté", "SkillKorp K20 n'est plus détecté.")
        self.last_connected = connected

        # Low battery warnings
        if connected and pct > 0:
            if pct <= 10 and not self.warned_low_10 and not charging:
                self._notify("Batterie Critique", f"SkillKorp K20 : {pct}% restant. Branchez le câble USB !", 2)
                self.warned_low_10 = True
            elif pct <= 20 and not self.warned_low_20 and not charging:
                self._notify("Batterie Faible", f"SkillKorp K20 : {pct}% restant.", 1)
                self.warned_low_20 = True
            elif pct > 30:
                self.warned_low_20 = False
                self.warned_low_10 = False

            # Label in panel
            charge_mark = " ⚡" if charging else ""
            self.indicator.set_label(f"{pct}%{charge_mark}", "100%")
        else:
            self.indicator.set_label("", "")

        # Update battery item text
        if connected:
            ch_str = " (En charge ⚡)" if charging else ""
            self.item_battery.set_label(f"Batterie : {pct}%{ch_str}")
        else:
            self.item_battery.set_label("Clavier déconnecté")

        # Update active profile label
        active_id = self.pm.get_active_profile_id()
        prof = self.pm.get_profile(active_id)
        p_name = prof.get("name", active_id) if prof else active_id
        self.item_profile_header.set_label(f"Profil : {p_name}")

        # Update Win Lock state
        opts = self.driver.config.get("options", {})
        win_lock = opts.get("win_lock", False)
        self.item_win_lock.set_active(win_lock)

    def _on_status_timer(self) -> bool:
        self._update_status()
        return True

    def _on_auto_switch_timer(self) -> bool:
        if not self.pm.is_auto_switch_enabled():
            return True

        cls = detect_active_window_class()
        if cls and cls != self.last_active_window:
            self.last_active_window = cls
            profiles = self.pm.list_profiles()
            matched_prof = None
            for p in profiles:
                for app in p.get("auto_switch_apps", []):
                    if app.lower() in cls:
                        matched_prof = p["id"]
                        break
                if matched_prof:
                    break

            if matched_prof and matched_prof != self.pm.get_active_profile_id():
                p = self.pm.switch_profile(matched_prof, driver=self.driver)
                self._update_status()
                self._notify("Profil automatique activé", f"Profil '{p.get('name', matched_prof)}' pour {cls}.")

        return True

    def _build_menu(self):
        # 1. Header with Battery info
        self.item_battery = Gtk.MenuItem(label="Batterie : --%")
        self.item_battery.set_sensitive(False)
        self.menu.append(self.item_battery)

        self.menu.append(Gtk.SeparatorMenuItem())

        # 2. Profiles Submenu
        self.item_profile_header = Gtk.MenuItem(label="Profil : Par défaut")
        self.profile_submenu = Gtk.Menu()
        self._populate_profile_submenu()
        self.item_profile_header.set_submenu(self.profile_submenu)
        self.menu.append(self.item_profile_header)

        # 3. RGB Backlight Effects Submenu
        item_rgb = Gtk.MenuItem(label="Éclairage RGB")
        rgb_submenu = Gtk.Menu()
        for key, name, _ in LIGHT_MODES:
            sub_item = Gtk.MenuItem(label=name)
            sub_item.connect("activate", lambda w, k=key: self._on_select_rgb(k))
            rgb_submenu.append(sub_item)
        item_rgb.set_submenu(rgb_submenu)
        self.menu.append(item_rgb)

        # 4. Polling Rate Submenu
        item_poll = Gtk.MenuItem(label="Taux de rafraîchissement")
        poll_submenu = Gtk.Menu()
        for hz in [1000, 500, 250, 125]:
            sub_item = Gtk.MenuItem(label=f"{hz} Hz")
            sub_item.connect("activate", lambda w, r=hz: self._on_select_poll(r))
            poll_submenu.append(sub_item)
        item_poll.set_submenu(poll_submenu)
        self.menu.append(item_poll)

        # 5. Windows Key Lock Toggle
        self.item_win_lock = Gtk.CheckMenuItem(label="Verrouiller touche Windows")
        self.item_win_lock.connect("toggled", self._on_toggle_win_lock)
        self.menu.append(self.item_win_lock)

        self.menu.append(Gtk.SeparatorMenuItem())

        # 6. Open GUI
        item_open_gui = Gtk.MenuItem(label="Ouvrir SkillKorp K20...")
        item_open_gui.connect("activate", self._on_open_gui)
        self.menu.append(item_open_gui)

        # 7. Autostart checkbox
        self.item_autostart = Gtk.CheckMenuItem(label="Lancer avec la session")
        self.item_autostart.set_active(is_autostart_enabled())
        self.item_autostart.connect("toggled", self._on_toggle_autostart)
        self.menu.append(self.item_autostart)

        self.menu.append(Gtk.SeparatorMenuItem())

        # 8. Quit
        item_quit = Gtk.MenuItem(label="Quitter")
        item_quit.connect("activate", self._on_quit)
        self.menu.append(item_quit)

        self.menu.show_all()

    def _populate_profile_submenu(self):
        for child in self.profile_submenu.get_children():
            self.profile_submenu.remove(child)

        profiles = self.pm.list_profiles()
        active_id = self.pm.get_active_profile_id()

        for p in profiles:
            p_id = p["id"]
            p_name = p.get("name", p_id)
            label = f"✓ {p_name}" if p_id == active_id else f"   {p_name}"
            sub_item = Gtk.MenuItem(label=label)
            sub_item.connect("activate", lambda w, pid=p_id: self._on_select_profile(pid))
            self.profile_submenu.append(sub_item)

        self.profile_submenu.show_all()

    def _on_select_profile(self, prof_id: str):
        try:
            prof = self.pm.switch_profile(prof_id, driver=self.driver)
            self._populate_profile_submenu()
            self._update_status()
            self._notify("Profil activé", f"Profil '{prof.get('name', prof_id)}' appliqué.")
        except Exception as e:
            print(f"Erreur sélection profil : {e}", file=sys.stderr)

    def _on_select_rgb(self, mode: str):
        self.driver.set_rgb(mode=mode)
        self._notify("Éclairage RGB", f"Effet '{mode}' appliqué.")

    def _on_select_poll(self, rate: int):
        self.driver.set_polling_rate(rate)
        self._notify("Taux de rafraîchissement", f"Configuré à {rate} Hz.")

    def _on_toggle_win_lock(self, item):
        target = item.get_active()
        self.driver.set_keyboard_options(win_lock=target)
        st = "verrouillée" if target else "déverrouillée"
        self._notify("Touche Windows", f"Touche Windows {st}.")

    def _on_toggle_autostart(self, item):
        set_autostart(item.get_active())

    def _on_open_gui(self, item):
        gui_path = os.path.join(BASE_DIR, "k20_gui.py")
        subprocess.Popen([sys.executable, gui_path])

    def _on_quit(self, item):
        Gtk.main_quit()


def main():
    app = K20TrayApp()
    Gtk.main()


if __name__ == "__main__":
    main()
