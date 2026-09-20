#!/usr/bin/env python3
"""
SkillKorp K20 Ultimate - Multi-Profile Manager & Auto-Switching
Manages persistent keyboard profiles and automatic switching based on active applications.
"""

import os
import sys
import json
import shutil
import subprocess
import re
from typing import Dict, List, Optional, Any

CONFIG_DIR = os.path.expanduser("~/.config/skillkorp-k20")
PROFILES_DIR = os.path.join(CONFIG_DIR, "profiles")
STATE_FILE = os.path.join(CONFIG_DIR, "profile_state.json")
AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, "io.github.skillkorp.k20.tray.desktop")


def is_autostart_enabled() -> bool:
    return os.path.exists(AUTOSTART_FILE)


def set_autostart(enabled: bool):
    os.makedirs(AUTOSTART_DIR, exist_ok=True)
    if enabled:
        content = """[Desktop Entry]
Type=Application
Name=SkillKorp K20 Tray
Comment=Indicateur de batterie et raccourcis SkillKorp K20
Exec=k20-tray
Icon=skillkorp-k20
Terminal=false
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
        with open(AUTOSTART_FILE, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        if os.path.exists(AUTOSTART_FILE):
            os.remove(AUTOSTART_FILE)


# Default profiles created on initial setup
DEFAULT_PROFILES: Dict[str, Dict[str, Any]] = {
    "default": {
        "id": "default",
        "name": "Par défaut",
        "description": "Configuration standard polyvalente (1000 Hz, effet Onde RGB)",
        "polling_rate": 1000,
        "debounce_ms": 8,
        "sleep": {
            "light_sleep_sec": 120,
            "deep_sleep_sec": 1680,
        },
        "options": {
            "win_lock": False,
            "wasd_swap": False,
            "os_mode": "win",
            "gaming_mode": False,
        },
        "rgb": {
            "mode": "wave",
            "speed": 3,
            "brightness": 4,
            "direction": 0,
            "color": "#FF0000",
        },
        "side_rgb": {
            "mode": "rainbow",
            "speed": 3,
            "brightness": 4,
            "color": "#00FFCC",
        },
        "key_remaps": {},
        "fn_remaps": {},
        "auto_switch_apps": [],
    },
    "gaming": {
        "id": "gaming",
        "name": "Gaming / Compétition",
        "description": "Performances maximales (1000 Hz, anti-rebond 2 ms, verrouillage touche Windows activé)",
        "polling_rate": 1000,
        "debounce_ms": 2,
        "sleep": {
            "light_sleep_sec": 300,
            "deep_sleep_sec": 3600,
        },
        "options": {
            "win_lock": True,
            "wasd_swap": False,
            "os_mode": "win",
            "gaming_mode": True,
        },
        "rgb": {
            "mode": "wave",
            "speed": 4,
            "brightness": 4,
            "direction": 0,
            "color": "#FF0055",
        },
        "side_rgb": {
            "mode": "rainbow",
            "speed": 4,
            "brightness": 4,
            "color": "#FF0055",
        },
        "key_remaps": {},
        "fn_remaps": {},
        "auto_switch_apps": ["steam", "lutris", "heroic", "cs2", "valorant", "dota2", "overwatch"],
    },
    "bureau": {
        "id": "bureau",
        "name": "Bureautique / Travail",
        "description": "Confort de frappe et économie d'énergie (500 Hz, éclairage discret)",
        "polling_rate": 500,
        "debounce_ms": 10,
        "sleep": {
            "light_sleep_sec": 120,
            "deep_sleep_sec": 1200,
        },
        "options": {
            "win_lock": False,
            "wasd_swap": False,
            "os_mode": "win",
            "gaming_mode": False,
        },
        "rgb": {
            "mode": "breathing",
            "speed": 2,
            "brightness": 2,
            "direction": 0,
            "color": "#0088FF",
        },
        "side_rgb": {
            "mode": "static",
            "speed": 2,
            "brightness": 2,
            "color": "#0088FF",
        },
        "key_remaps": {},
        "fn_remaps": {},
        "auto_switch_apps": ["code", "libreoffice", "firefox", "chromium", "thunderbird", "slack"],
    },
    "eco": {
        "id": "eco",
        "name": "Nuit & Économie d'énergie",
        "description": "Autonomie maximale en sans-fil (125 Hz, luminosité faible, mise en veille rapide)",
        "polling_rate": 125,
        "debounce_ms": 12,
        "sleep": {
            "light_sleep_sec": 30,
            "deep_sleep_sec": 600,
        },
        "options": {
            "win_lock": False,
            "wasd_swap": False,
            "os_mode": "win",
            "gaming_mode": False,
        },
        "rgb": {
            "mode": "static",
            "speed": 1,
            "brightness": 1,
            "direction": 0,
            "color": "#FFAA00",
        },
        "side_rgb": {
            "mode": "off",
            "speed": 1,
            "brightness": 0,
            "color": "#000000",
        },
        "key_remaps": {},
        "fn_remaps": {},
        "auto_switch_apps": [],
    },
}


class ProfileManager:
    """Manages multi-profile storage, active profile state, and hardware synchronization."""

    def __init__(self):
        os.makedirs(PROFILES_DIR, exist_ok=True)
        self._ensure_default_profiles()

    def _ensure_default_profiles(self):
        for prof_id, data in DEFAULT_PROFILES.items():
            path = self._get_profile_path(prof_id)
            if not os.path.exists(path):
                self._save_profile_file(path, data)

    def _get_profile_path(self, prof_id: str) -> str:
        return os.path.join(PROFILES_DIR, f"{prof_id}.json")

    def _load_state(self) -> Dict[str, Any]:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"active_profile": "default", "auto_switch_enabled": True}

    def _save_state(self, state: Dict[str, Any]):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def _save_profile_file(self, path: str, data: Dict[str, Any]):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def is_auto_switch_enabled(self) -> bool:
        return self._load_state().get("auto_switch_enabled", True)

    def set_auto_switch_enabled(self, enabled: bool):
        st = self._load_state()
        st["auto_switch_enabled"] = bool(enabled)
        self._save_state(st)

    def get_active_profile_id(self) -> str:
        return self._load_state().get("active_profile", "default")

    def list_profiles(self) -> List[Dict[str, Any]]:
        active_id = self.get_active_profile_id()
        profiles = []
        if os.path.exists(PROFILES_DIR):
            for fname in sorted(os.listdir(PROFILES_DIR)):
                if fname.endswith(".json"):
                    prof_id = fname[:-5]
                    prof = self.get_profile(prof_id)
                    if prof:
                        prof["active"] = (prof_id == active_id)
                        profiles.append(prof)
        return profiles

    def get_profile(self, prof_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_profile_path(prof_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["id"] = prof_id
                return data
        except Exception as e:
            print(f"[ProfileManager] Erreur chargement {path}: {e}", file=sys.stderr)
            return None

    def save_profile(self, prof_id: str, data: Dict[str, Any]):
        path = self._get_profile_path(prof_id)
        data["id"] = prof_id
        self._save_profile_file(path, data)

    def create_profile(self, prof_id: str, name: str, copy_from: Optional[str] = None) -> Dict[str, Any]:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", prof_id).lower()
        if copy_from:
            source = self.get_profile(copy_from)
        else:
            source = self.get_profile("default")

        if not source:
            source = DEFAULT_PROFILES["default"].copy()

        new_data = json.loads(json.dumps(source))
        new_data["id"] = safe_id
        new_data["name"] = name
        new_data["description"] = f"Profil personnalisé : {name}"
        new_data["auto_switch_apps"] = []
        self.save_profile(safe_id, new_data)
        return new_data

    def delete_profile(self, prof_id: str) -> bool:
        if prof_id == "default":
            raise ValueError("Le profil 'default' ne peut pas être supprimé.")
        path = self._get_profile_path(prof_id)
        if os.path.exists(path):
            os.remove(path)
            if self.get_active_profile_id() == prof_id:
                self.switch_profile("default")
            return True
        return False

    def export_profile(self, prof_id: str, target_file: str) -> bool:
        prof = self.get_profile(prof_id)
        if not prof:
            raise ValueError(f"Profil '{prof_id}' introuvable.")
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(prof, f, indent=2, ensure_ascii=False)
        return True

    def import_profile(self, source_file: str, new_id: Optional[str] = None) -> str:
        """Import a profile from a JSON file with validation."""
        with open(source_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("Le fichier de profil doit être un objet JSON.")

        # Validate polling_rate
        valid_rates = [125, 250, 500, 1000]
        rate = data.get("polling_rate")
        if rate is not None and rate not in valid_rates:
            raise ValueError(f"polling_rate invalide: {rate}. Choix acceptés: {valid_rates}.")

        # Validate debounce
        debounce = data.get("debounce_ms")
        if debounce is not None and (not isinstance(debounce, int) or not (2 <= debounce <= 20)):
            raise ValueError(f"debounce_ms invalide: {debounce} (doit être entre 2 et 20 ms).")

        prof_id = new_id or data.get("id") or os.path.basename(source_file).replace(".json", "")
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", prof_id).lower()
        data["id"] = safe_id
        self.save_profile(safe_id, data)
        return safe_id

    def switch_profile(self, prof_id: str, driver: Optional[Any] = None) -> Dict[str, Any]:
        prof = self.get_profile(prof_id)
        if not prof:
            raise ValueError(f"Profil '{prof_id}' introuvable.")

        # Update active state
        st = self._load_state()
        st["active_profile"] = prof_id
        self._save_state(st)

        # Apply settings to driver and hardware if driver is provided
        if driver is not None:
            self.apply_profile_to_driver(prof, driver)

        return prof

    def apply_profile_to_driver(self, prof: Dict[str, Any], driver: Any):
        """Applies profile configuration parameters directly to driver and hardware."""
        if hasattr(driver, "apply_profile"):
            driver.apply_profile(prof)


def detect_active_window_class() -> Optional[str]:
    """Detect active window process name or WM_CLASS on Linux (X11 & Wayland)."""
    # 1. Try xdotool (fastest on X11 / XWayland)
    try:
        out = subprocess.check_output(
            ["xdotool", "getactivewindow", "getwindowclassname"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.3,
        ).strip()
        if out:
            return out.lower()
    except Exception:
        pass

    # 2. Try xprop
    try:
        out = subprocess.check_output(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.3,
        ).strip()
        win_id = out.split()[-1]
        if win_id and win_id != "0x0":
            prop_out = subprocess.check_output(
                ["xprop", "-id", win_id, "WM_CLASS"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=0.3,
            ).strip()
            matches = re.findall(r'"([^"]+)"', prop_out)
            if matches:
                return matches[-1].lower()
    except Exception:
        pass

    # 3. Try hyprctl (Wayland Hyprland)
    try:
        out = subprocess.check_output(
            ["hyprctl", "activewindow", "-j"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.3,
        )
        data = json.loads(out)
        cls = data.get("class")
        if cls:
            return cls.lower()
    except Exception:
        pass

    # 4. Try swaymsg (Wayland Sway)
    try:
        out = subprocess.check_output(
            ["swaymsg", "-t", "get_tree"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.4,
        )
        data = json.loads(out)
        def find_focused(node):
            if node.get("focused"):
                return node.get("app_id") or node.get("window_properties", {}).get("class")
            for ch in node.get("nodes", []) + node.get("floating_nodes", []):
                res = find_focused(ch)
                if res:
                    return res
            return None
        res = find_focused(data)
        if res:
            return res.lower()
    except Exception:
        pass

    return None
