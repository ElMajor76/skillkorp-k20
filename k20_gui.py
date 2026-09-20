#!/usr/bin/env python3
"""
SkillKorp K20 Ultimate - Application Graphique Linux (GTK 4 / Libadwaita)
Fonctionnalités :
- Gestion multi-profils (Défaut, Gaming, Bureautique, Nuit/Éco, Profils personnalisés)
- Bascule automatique des profils selon l'application active
- Éclairage RGB des touches (10 effets, vitesse, luminosité, direction, palette & couleur personnalisée)
- Bandes LED latérales RGB
- Taux de rafraîchissement (125 Hz à 1000 Hz) et filtre anti-rebond (2 ms à 20 ms)
- Délais de veille matérielle (légère et profonde)
- Options matérielles: Verrouillage touche Windows, Inversion ZQSD/Flèches, Mode OS, Mode Gaming
- Visualisation interactive du clavier 75% AZERTY et remappage des touches
- Indicateur barre des tâches et autostart
"""

import sys
import os
import time
import subprocess
from typing import Optional, Dict, List, Any

# Ensure project directory is in python path
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, BASE_DIR)
from k20_driver import (
    SkillkorpK20Driver,
    LIGHT_MODES,
    LIGHT_CODE_BY_KEY,
    LIGHT_MODE_BY_CODE,
    SIDE_LIGHT_MODES,
    SIDE_LIGHT_CODE_BY_KEY,
    POLLING_RATE_MAP,
    REMAP_ACTIONS,
    KEY_LAYOUT,
)
from profile_manager import (
    ProfileManager,
    detect_active_window_class,
    is_autostart_enabled,
    set_autostart,
)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk, GObject


class SkillkorpK20Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="SkillKorp K20 Ultimate")
        self.set_default_size(1020, 780)
        self.set_size_request(850, 650)
        self.add_css_class("preferences")

        self.driver = SkillkorpK20Driver()
        self.pm = ProfileManager()
        self._updating_ui = False

        # Custom styling
        css_provider = Gtk.CssProvider()
        css_provider.load_from_string("""
        .status-pill-connected {
            background-color: rgba(46, 194, 89, 0.2);
            color: #2ec259;
            border-radius: 12px;
            padding: 4px 10px;
            font-weight: bold;
            font-size: 0.85em;
        }
        .status-pill-disconnected {
            background-color: rgba(224, 27, 36, 0.2);
            color: #e01b24;
            border-radius: 12px;
            padding: 4px 10px;
            font-weight: bold;
            font-size: 0.85em;
        }
        .color-palette-btn {
            min-width: 28px;
            min-height: 28px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            margin: 2px;
            padding: 0;
        }
        .keyboard-preview-container {
            background-color: rgba(0, 0, 0, 0.15);
            border-radius: 12px;
            padding: 16px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        .color-swatch-red { background-color: #FF0000; }
        .color-swatch-orange { background-color: #FF7700; }
        .color-swatch-yellow { background-color: #FFFF00; }
        .color-swatch-green { background-color: #00FF00; }
        .color-swatch-cyan { background-color: #00FFFF; }
        .color-swatch-blue { background-color: #0066FF; }
        .color-swatch-purple { background-color: #9900FF; }
        .color-swatch-pink { background-color: #FF00AA; }
        .color-swatch-white { background-color: #FFFFFF; }
        """)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

        # Main layout structure: ToolbarView with HeaderBar & ViewSwitcherTitle
        self.toolbar_view = Adw.ToolbarView()
        self.view_stack = Adw.ViewStack()

        self.view_switcher_title = Adw.ViewSwitcherTitle(
            stack=self.view_stack,
            title="SkillKorp K20 Ultimate",
        )

        self.header_bar = Adw.HeaderBar(title_widget=self.view_switcher_title)

        # Connection status pill in header
        self.status_pill = Gtk.Label(label="Connecté")
        self.status_pill.add_css_class("status-pill-connected")
        self.header_bar.pack_start(self.status_pill)

        # Battery indicator in header
        self.battery_button = Gtk.Button()
        self.battery_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.battery_icon = Gtk.Image.new_from_icon_name("battery-level-80-symbolic")
        self.battery_label = Gtk.Label(label="--%")
        self.battery_box.append(self.battery_icon)
        self.battery_box.append(self.battery_label)
        self.battery_button.set_child(self.battery_box)
        self.battery_button.set_tooltip_text("État de la batterie")
        self.battery_button.connect("clicked", self._on_battery_clicked)
        self.header_bar.pack_end(self.battery_button)

        # Reload button
        self.reload_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        self.reload_btn.set_tooltip_text("Actualiser l'état du clavier")
        self.reload_btn.connect("clicked", lambda b: self._reload_status())
        self.header_bar.pack_end(self.reload_btn)

        # Primary Menu
        menu = Gio.Menu()
        menu.append("Réinitialiser les réglages d'usine", "app.factory_reset")
        menu.append("À propos de SkillKorp K20", "app.about")
        self.menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        self.header_bar.pack_end(self.menu_button)

        self.toolbar_view.add_top_bar(self.header_bar)

        # Bottom Bar for mobile/narrow viewports
        self.view_switcher_bar = Adw.ViewSwitcherBar(stack=self.view_stack)
        self.view_switcher_title.bind_property(
            "title-visible",
            self.view_switcher_bar,
            "reveal",
            GObject.BindingFlags.SYNC_CREATE,
        )
        self.toolbar_view.add_bottom_bar(self.view_switcher_bar)

        # Connection banner
        self.banner = Adw.Banner(
            title="Clavier SkillKorp K20 non détecté. Branchez le récepteur 2.4GHz ou le câble USB-C.",
            revealed=False,
            button_label="Actualiser",
        )
        self.banner.connect("button-clicked", lambda b: self._reload_status())

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(self.banner)
        main_box.append(self.view_stack)

        self.toast_overlay = Adw.ToastOverlay(child=main_box)
        self.toolbar_view.set_content(self.toast_overlay)
        self.set_content(self.toolbar_view)

        # Build UI Tabs
        self._build_rgb_page()
        self._build_perf_page()
        self._build_options_page()
        self._build_profiles_page()

        # Initial UI synchronization
        self._sync_ui_from_driver()

        # Background battery & connection monitor (every 4 seconds)
        GLib.timeout_add_seconds(4, self._on_status_poll_timer)

    # =========================================================================
    # Tab 1: Éclairage RGB
    # =========================================================================

    def _build_rgb_page(self):
        page = Adw.PreferencesPage()
        page.set_title("Éclairage RGB")
        page.set_icon_name("weather-clear-symbolic")

        # 1. Main Key Backlight
        rgb_group = Adw.PreferencesGroup(
            title="Rétroéclairage des Touches",
            description="Personnalisez les effets lumineux, la vitesse et la luminosité du clavier.",
        )

        # Effect Dropdown
        self.rgb_mode_row = Adw.ComboRow(title="Effet d'éclairage")
        model = Gtk.StringList()
        for key, name, _ in LIGHT_MODES:
            model.append(name)
        self.rgb_mode_row.set_model(model)
        self.rgb_mode_row.connect("notify::selected", self._on_rgb_mode_changed)
        rgb_group.add(self.rgb_mode_row)

        # Speed Scale (1 to 5)
        self.rgb_speed_row = Adw.ActionRow(title="Vitesse de l'effet")
        self.rgb_speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 5, 1)
        self.rgb_speed_scale.set_draw_value(True)
        self.rgb_speed_scale.set_size_request(220, -1)
        self.rgb_speed_scale.connect("value-changed", self._on_rgb_speed_changed)
        self.rgb_speed_row.add_suffix(self.rgb_speed_scale)
        rgb_group.add(self.rgb_speed_row)

        # Brightness Scale (0 to 4)
        self.rgb_bright_row = Adw.ActionRow(title="Luminosité")
        self.rgb_bright_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 4, 1)
        self.rgb_bright_scale.set_draw_value(True)
        self.rgb_bright_scale.set_size_request(220, -1)
        self.rgb_bright_scale.connect("value-changed", self._on_rgb_bright_changed)
        self.rgb_bright_row.add_suffix(self.rgb_bright_scale)
        rgb_group.add(self.rgb_bright_row)

        # Direction Switch (Right vs Left)
        self.rgb_dir_row = Adw.SwitchRow(
            title="Direction de l'onde",
            subtitle="Désactivé : Droite vers Gauche | Activé : Gauche vers Droite",
        )
        self.rgb_dir_row.connect("notify::active", self._on_rgb_dir_changed)
        rgb_group.add(self.rgb_dir_row)

        # Color Palette Row
        self.rgb_color_row = Adw.ActionRow(title="Couleur personnalisée", subtitle="Sélectionnez une teinte fixe ou personnalisée")
        palette_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        colors = [
            ("#FF0000", "Rouge", "color-swatch-red"),
            ("#FF7700", "Orange", "color-swatch-orange"),
            ("#FFFF00", "Jaune", "color-swatch-yellow"),
            ("#00FF00", "Vert", "color-swatch-green"),
            ("#00FFFF", "Cyan", "color-swatch-cyan"),
            ("#0066FF", "Bleu", "color-swatch-blue"),
            ("#9900FF", "Violet", "color-swatch-purple"),
            ("#FF00AA", "Rose", "color-swatch-pink"),
            ("#FFFFFF", "Blanc", "color-swatch-white"),
        ]
        for hex_col, name, css_cls in colors:
            btn = Gtk.Button()
            btn.add_css_class("color-palette-btn")
            btn.add_css_class(css_cls)
            btn.set_tooltip_text(name)
            btn.connect("clicked", lambda b, c=hex_col: self._on_palette_color_clicked(c))
            palette_box.append(btn)

        self.color_dialog_btn = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog())
        self.color_dialog_btn.connect("notify::rgba", self._on_color_dialog_changed)
        palette_box.append(self.color_dialog_btn)

        self.rgb_color_row.add_suffix(palette_box)
        rgb_group.add(self.rgb_color_row)
        page.add(rgb_group)

        # 2. Side RGB LED Strips
        side_group = Adw.PreferencesGroup(
            title="Bandes LED Latérales",
            description="Contrôle des diffuseurs lumineux latéraux gauche et droit.",
        )

        self.side_mode_row = Adw.ComboRow(title="Effet latéral")
        smodel = Gtk.StringList()
        for key, name, _ in SIDE_LIGHT_MODES:
            smodel.append(name)
        self.side_mode_row.set_model(smodel)
        self.side_mode_row.connect("notify::selected", self._on_side_mode_changed)
        side_group.add(self.side_mode_row)

        self.side_bright_row = Adw.ActionRow(title="Luminosité latérale")
        self.side_bright_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 4, 1)
        self.side_bright_scale.set_draw_value(True)
        self.side_bright_scale.set_size_request(220, -1)
        self.side_bright_scale.connect("value-changed", self._on_side_bright_changed)
        self.side_bright_row.add_suffix(self.side_bright_scale)
        side_group.add(self.side_bright_row)

        page.add(side_group)
        self.view_stack.add_titled(page, "rgb", "Éclairage RGB").set_icon_name("weather-clear-symbolic")

    # =========================================================================
    # Tab 2: Performance & Veille
    # =========================================================================

    def _build_perf_page(self):
        page = Adw.PreferencesPage()
        page.set_title("Performance")
        page.set_icon_name("speedometer-symbolic")

        # Polling rate and debounce
        perf_group = Adw.PreferencesGroup(
            title="Fréquence et Réactivité",
            description="Ajustez la cadence de communication USB et le filtrage mécanique des commutateurs.",
        )

        self.poll_row = Adw.ComboRow(title="Taux de rafraîchissement (Polling Rate)")
        pmodel = Gtk.StringList()
        for hz in [1000, 500, 250, 125]:
            desc = "Recommandé pour le jeu (1 ms)" if hz == 1000 else "Standard" if hz == 500 else "Éco"
            pmodel.append(f"{hz} Hz - {desc}")
        self.poll_row.set_model(pmodel)
        self.poll_row.connect("notify::selected", self._on_poll_changed)
        perf_group.add(self.poll_row)

        self.deb_row = Adw.ActionRow(
            title="Temps d'anti-rebond (Debounce)",
            subtitle="Plus faible = temps de réaction ultra-rapide (2 ms conseillé pour le gaming compétitif)",
        )
        self.deb_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 2, 20, 1)
        self.deb_scale.set_draw_value(True)
        self.deb_scale.set_size_request(220, -1)
        self.deb_scale.connect("value-changed", self._on_deb_changed)
        self.deb_row.add_suffix(self.deb_scale)
        perf_group.add(self.deb_row)
        page.add(perf_group)

        # Power & Sleep
        sleep_group = Adw.PreferencesGroup(
            title="Gestion de l'Alimentation et Veille",
            description="Économise la batterie en mode sans-fil 2.4GHz lors des périodes d'inactivité.",
        )

        self.light_sleep_row = Adw.ActionRow(
            title="Veille légère (Extinction RGB)",
            subtitle="Éteint le rétroéclairage après inactivité (rallumage instantané à la frappe)",
        )
        self.light_sleep_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 600, 10)
        self.light_sleep_scale.set_draw_value(True)
        self.light_sleep_scale.set_size_request(220, -1)
        self.light_sleep_scale.connect("value-changed", self._on_sleep_changed)
        self.light_sleep_row.add_suffix(self.light_sleep_scale)
        sleep_group.add(self.light_sleep_row)

        self.deep_sleep_row = Adw.ActionRow(
            title="Veille profonde (Coupure radio)",
            subtitle="Coupe la liaison radio sans-fil après longue inactivité pour préserver la batterie",
        )
        self.deep_sleep_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 600, 7200, 60)
        self.deep_sleep_scale.set_draw_value(True)
        self.deep_sleep_scale.set_size_request(220, -1)
        self.deep_sleep_scale.connect("value-changed", self._on_sleep_changed)
        self.deep_sleep_row.add_suffix(self.deep_sleep_scale)
        sleep_group.add(self.deep_sleep_row)

        page.add(sleep_group)
        self.view_stack.add_titled(page, "perf", "Performance").set_icon_name("speedometer-symbolic")

    # =========================================================================
    # Tab 3: Options Clavier & Mappage
    # =========================================================================

    def _build_options_page(self):
        page = Adw.PreferencesPage()
        page.set_title("Clavier")
        page.set_icon_name("input-keyboard-symbolic")

        # Switches & options
        opts_group = Adw.PreferencesGroup(
            title="Options Matérielles",
            description="Fonctions avancées intégrées au microprogramme du clavier.",
        )

        self.win_lock_row = Adw.SwitchRow(
            title="Verrouiller la touche Windows",
            subtitle="Empêche les retours inopinés sur le bureau pendant les sessions de jeu",
        )
        self.win_lock_row.connect("notify::active", self._on_win_lock_changed)
        opts_group.add(self.win_lock_row)

        self.wasd_swap_row = Adw.SwitchRow(
            title="Échanger ZQSD et les Flèches",
            subtitle="Permet de diriger les déplacements avec ZQSD ou les touches directionnelles",
        )
        self.wasd_swap_row.connect("notify::active", self._on_wasd_swap_changed)
        opts_group.add(self.wasd_swap_row)

        self.gaming_mode_row = Adw.SwitchRow(
            title="Mode Gaming",
            subtitle="Priorité maximale au traitement des frappes simultanées (N-Key Rollover optimisé)",
        )
        self.gaming_mode_row.connect("notify::active", self._on_gaming_mode_changed)
        opts_group.add(self.gaming_mode_row)

        self.os_mode_row = Adw.ComboRow(title="Système d'exploitation cible")
        os_model = Gtk.StringList()
        os_model.append("Windows / Linux (Défaut)")
        os_model.append("macOS (Inversion Cmd/Option)")
        os_model.append("iOS")
        os_model.append("Android")
        self.os_mode_row.set_model(os_model)
        self.os_mode_row.connect("notify::selected", self._on_os_mode_changed)
        opts_group.add(self.os_mode_row)

        page.add(opts_group)

        # Interactive Key Remapping Group
        remap_group = Adw.PreferencesGroup(
            title="Disposition et Remappage des Touches",
            description="Format compact 75% (84 touches, disposition AZERTY France).",
        )

        # Keyboard graphic preview card
        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        preview_box.add_css_class("keyboard-preview-container")

        img_path = os.path.join(BASE_DIR, "assets", "keyboard.png")
        if os.path.exists(img_path):
            kb_img = Gtk.Image.new_from_file(img_path)
            kb_img.set_pixel_size(480)
            preview_box.append(kb_img)

        remap_group.add(preview_box)

        # Key Selector & Action Assign
        remap_ctrl_box = Adw.ActionRow(title="Modifier l'action d'une touche")
        ctrl_h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        self.key_selector_combo = Gtk.DropDown()
        key_names = [k["name"] for k in KEY_LAYOUT]
        k_model = Gtk.StringList()
        for kn in key_names:
            k_model.append(kn)
        self.key_selector_combo.set_model(k_model)
        ctrl_h_box.append(self.key_selector_combo)

        lbl_to = Gtk.Label(label="➔")
        ctrl_h_box.append(lbl_to)

        self.action_selector_combo = Gtk.DropDown()
        act_model = Gtk.StringList()
        self.remap_action_keys = list(REMAP_ACTIONS.keys())
        for ak in self.remap_action_keys:
            act_model.append(REMAP_ACTIONS[ak][0])
        self.action_selector_combo.set_model(act_model)
        ctrl_h_box.append(self.action_selector_combo)

        self.btn_apply_remap = Gtk.Button(label="Assigner")
        self.btn_apply_remap.add_css_class("suggested-action")
        self.btn_apply_remap.connect("clicked", self._on_apply_remap_clicked)
        ctrl_h_box.append(self.btn_apply_remap)

        remap_ctrl_box.add_suffix(ctrl_h_box)
        remap_group.add(remap_ctrl_box)

        page.add(remap_group)
        self.view_stack.add_titled(page, "options", "Clavier").set_icon_name("input-keyboard-symbolic")

    # =========================================================================
    # Tab 4: Profils
    # =========================================================================

    def _build_profiles_page(self):
        page = Adw.PreferencesPage()
        page.set_title("Profils")
        page.set_icon_name("folder-symbolic")

        self.profiles_group = Adw.PreferencesGroup(
            title="Profil Actif",
            description="Sélectionnez ou gérez vos profils de configuration.",
        )

        header_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_new_prof = Gtk.Button(label="Nouveau profil", icon_name="list-add-symbolic")
        btn_new_prof.connect("clicked", self._on_new_profile_clicked)
        header_btn_box.append(btn_new_prof)

        btn_import_prof = Gtk.Button(label="Importer", icon_name="document-open-symbolic")
        btn_import_prof.connect("clicked", self._on_import_profile_clicked)
        header_btn_box.append(btn_import_prof)
        self.profiles_group.set_header_suffix(header_btn_box)

        self.profile_combo = Adw.ComboRow(title="Profil en cours d'utilisation")
        self.profile_combo.connect("notify::selected", self._on_profile_combo_changed)
        self.profiles_group.add(self.profile_combo)

        page.add(self.profiles_group)

        # Profile details & actions
        self.profiles_list_group = Adw.PreferencesGroup(
            title="Profils Enregistrés",
            description="Liste détaillée des profils stockés.",
        )
        page.add(self.profiles_list_group)

        # Auto-switch & Autostart options
        auto_group = Adw.PreferencesGroup(
            title="Automatisation et Intégration",
            description="Basculez de profil selon l'application ouverte et lancez l'application en arrière-plan.",
        )

        self.auto_switch_row = Adw.SwitchRow(
            title="Bascule automatique des profils",
            subtitle="Détecte la fenêtre active pour appliquer le profil correspondant",
        )
        self.auto_switch_row.set_active(self.pm.is_auto_switch_enabled())
        self.auto_switch_row.connect("notify::active", self._on_auto_switch_toggled)
        auto_group.add(self.auto_switch_row)

        self.autostart_row = Adw.SwitchRow(
            title="Démarrer automatiquement avec la session",
            subtitle="Lance l'indicateur dans la barre des tâches au démarrage du système",
        )
        self.autostart_row.set_active(is_autostart_enabled())
        self.autostart_row.connect("notify::active", self._on_autostart_toggled)
        auto_group.add(self.autostart_row)

        page.add(auto_group)
        self.view_stack.add_titled(page, "profiles", "Profils").set_icon_name("folder-symbolic")

        self._refresh_profiles_list()

    # =========================================================================
    # UI Synchronization & Handlers
    # =========================================================================

    def _sync_ui_from_driver(self):
        """Synchronize UI control values from current driver configuration."""
        self._updating_ui = True
        try:
            self.driver.reload_config_if_changed()
            cfg = self.driver.config

            # RGB
            rgb = cfg.get("rgb", {})
            cur_mode = rgb.get("mode", "wave")
            mode_idx = 0
            for idx, (k, _, _) in enumerate(LIGHT_MODES):
                if k == cur_mode:
                    mode_idx = idx
                    break
            self.rgb_mode_row.set_selected(mode_idx)
            self.rgb_speed_scale.set_value(rgb.get("speed", 3))
            self.rgb_bright_scale.set_value(rgb.get("brightness", 4))
            self.rgb_dir_row.set_active(rgb.get("direction", 0) == 1)

            # Side RGB
            srgb = cfg.get("side_rgb", {})
            cur_smode = srgb.get("mode", "rainbow")
            smode_idx = 0
            for idx, (k, _, _) in enumerate(SIDE_LIGHT_MODES):
                if k == cur_smode:
                    smode_idx = idx
                    break
            self.side_mode_row.set_selected(smode_idx)
            self.side_bright_scale.set_value(srgb.get("brightness", 4))

            # Performance
            rate = cfg.get("polling_rate", 1000)
            rate_map = {1000: 0, 500: 1, 250: 2, 125: 3}
            self.poll_row.set_selected(rate_map.get(rate, 0))
            self.deb_scale.set_value(cfg.get("debounce_ms", 8))

            # Sleep
            sleep = cfg.get("sleep", {})
            self.light_sleep_scale.set_value(sleep.get("light_sleep_sec", 120))
            self.deep_sleep_scale.set_value(sleep.get("deep_sleep_sec", 1680))

            # Options
            opts = cfg.get("options", {})
            self.win_lock_row.set_active(opts.get("win_lock", False))
            self.wasd_swap_row.set_active(opts.get("wasd_swap", False))
            self.gaming_mode_row.set_active(opts.get("gaming_mode", False))

            os_mode_map = {"win": 0, "mac": 1, "ios": 2, "android": 3}
            self.os_mode_row.set_selected(os_mode_map.get(opts.get("os_mode", "win"), 0))

            # Update battery & connection banner
            self._update_connection_status()

        finally:
            self._updating_ui = False

    def _update_connection_status(self):
        connected = self.driver.is_connected()
        is_wl = self.driver.is_wireless()
        self.banner.set_revealed(not connected)

        if connected:
            txt = "Connecté (Sans-fil 2.4GHz)" if is_wl else "Connecté (Câblé USB)"
            self.status_pill.set_label(txt)
            self.status_pill.remove_css_class("status-pill-disconnected")
            self.status_pill.add_css_class("status-pill-connected")

            bat = self.driver.get_battery()
            pct = bat.get("percentage") or 0
            icon_name = "battery-level-100-charged-symbolic" if bat.get("charging") else f"battery-level-{(pct//10)*10}-symbolic"
            self.battery_icon.set_from_icon_name(icon_name)
            self.battery_label.set_label(f"{pct}%")
            self.battery_button.set_tooltip_text(bat.get("status_str", ""))
        else:
            self.status_pill.set_label("Déconnecté")
            self.status_pill.remove_css_class("status-pill-connected")
            self.status_pill.add_css_class("status-pill-disconnected")
            self.battery_label.set_label("--%")
            self.battery_icon.set_from_icon_name("battery-missing-symbolic")

    def _on_status_poll_timer(self) -> bool:
        self._update_connection_status()
        return True

    def _reload_status(self):
        self.driver.dev_path = self.driver.find_device()
        self._sync_ui_from_driver()

    # Event handlers for controls
    def _on_rgb_mode_changed(self, row, param):
        if self._updating_ui: return
        idx = row.get_selected()
        mode_key = LIGHT_MODES[idx][0]
        self.driver.set_rgb(
            mode=mode_key,
            speed=int(self.rgb_speed_scale.get_value()),
            brightness=int(self.rgb_bright_scale.get_value()),
            direction=1 if self.rgb_dir_row.get_active() else 0,
        )

    def _on_rgb_speed_changed(self, scale):
        if self._updating_ui: return
        self.driver.set_rgb(
            mode=LIGHT_MODES[self.rgb_mode_row.get_selected()][0],
            speed=int(scale.get_value()),
            brightness=int(self.rgb_bright_scale.get_value()),
            direction=1 if self.rgb_dir_row.get_active() else 0,
        )

    def _on_rgb_bright_changed(self, scale):
        if self._updating_ui: return
        self.driver.set_rgb(
            mode=LIGHT_MODES[self.rgb_mode_row.get_selected()][0],
            speed=int(self.rgb_speed_scale.get_value()),
            brightness=int(scale.get_value()),
            direction=1 if self.rgb_dir_row.get_active() else 0,
        )

    def _on_rgb_dir_changed(self, row, param):
        if self._updating_ui: return
        self.driver.set_rgb(
            mode=LIGHT_MODES[self.rgb_mode_row.get_selected()][0],
            speed=int(self.rgb_speed_scale.get_value()),
            brightness=int(self.rgb_bright_scale.get_value()),
            direction=1 if row.get_active() else 0,
        )

    def _on_palette_color_clicked(self, hex_col: str):
        self.driver.set_rgb(
            mode="static",
            speed=int(self.rgb_speed_scale.get_value()),
            brightness=int(self.rgb_bright_scale.get_value()),
            color=hex_col,
        )
        self.rgb_mode_row.set_selected(1)  # static

    def _on_color_dialog_changed(self, btn, param):
        rgba = btn.get_rgba()
        r = int(rgba.red * 255)
        g = int(rgba.green * 255)
        b = int(rgba.blue * 255)
        hex_col = f"#{r:02X}{g:02X}{b:02X}"
        self._on_palette_color_clicked(hex_col)

    def _on_side_mode_changed(self, row, param):
        if self._updating_ui: return
        idx = row.get_selected()
        smode_key = SIDE_LIGHT_MODES[idx][0]
        self.driver.set_side_rgb(
            mode=smode_key,
            brightness=int(self.side_bright_scale.get_value()),
        )

    def _on_side_bright_changed(self, scale):
        if self._updating_ui: return
        self.driver.set_side_rgb(
            mode=SIDE_LIGHT_MODES[self.side_mode_row.get_selected()][0],
            brightness=int(scale.get_value()),
        )

    def _on_poll_changed(self, row, param):
        if self._updating_ui: return
        hz_list = [1000, 500, 250, 125]
        rate = hz_list[row.get_selected()]
        self.driver.set_polling_rate(rate)

    def _on_deb_changed(self, scale):
        if self._updating_ui: return
        self.driver.set_debounce(int(scale.get_value()))

    def _on_sleep_changed(self, scale):
        if self._updating_ui: return
        self.driver.set_sleep_time(
            light_sleep_sec=int(self.light_sleep_scale.get_value()),
            deep_sleep_sec=int(self.deep_sleep_scale.get_value()),
        )

    def _on_win_lock_changed(self, row, param):
        if self._updating_ui: return
        self.driver.set_keyboard_options(win_lock=row.get_active())

    def _on_wasd_swap_changed(self, row, param):
        if self._updating_ui: return
        self.driver.set_keyboard_options(wasd_swap=row.get_active())

    def _on_gaming_mode_changed(self, row, param):
        if self._updating_ui: return
        self.driver.set_keyboard_options(gaming_mode=row.get_active())

    def _on_os_mode_changed(self, row, param):
        if self._updating_ui: return
        modes = ["win", "mac", "ios", "android"]
        self.driver.set_keyboard_options(os_mode=modes[row.get_selected()])

    def _on_apply_remap_clicked(self, btn):
        key_idx = self.key_selector_combo.get_selected()
        key_name = KEY_LAYOUT[key_idx]["name"]
        act_idx = self.action_selector_combo.get_selected()
        action_key = self.remap_action_keys[act_idx]
        try:
            self.driver.remap_key(key_name, action_key)
            self._show_toast(f"Touche '{key_name}' remappée vers '{REMAP_ACTIONS[action_key][0]}'")
        except Exception as e:
            self._show_toast(f"Erreur: {e}")

    def _on_battery_clicked(self, btn):
        bat = self.driver.get_battery()
        msg = f"Niveau: {bat.get('percentage')}%\nStatut: {bat.get('status_str')}"
        self._show_toast(msg)

    def _refresh_profiles_list(self):
        old_updating = self._updating_ui
        self._updating_ui = True
        try:
            profiles = self.pm.list_profiles()
            self.profile_ids = [p["id"] for p in profiles]
            labels = [f"{p.get('name', p['id'])} ({p.get('description', '')})" for p in profiles]
            string_list = Gtk.StringList.new(labels)
            self.profile_combo.set_model(string_list)

            cur_id = self.pm.get_active_profile_id()
            if cur_id in self.profile_ids:
                self.profile_combo.set_selected(self.profile_ids.index(cur_id))
        finally:
            self._updating_ui = old_updating

    def _on_profile_combo_changed(self, row, param):
        if self._updating_ui: return
        idx = row.get_selected()
        if hasattr(self, "profile_ids") and 0 <= idx < len(self.profile_ids):
            target_id = self.profile_ids[idx]
            cur_id = self.pm.get_active_profile_id()
            if target_id != cur_id:
                try:
                    prof = self.pm.switch_profile(target_id, driver=self.driver)
                    self._sync_ui_from_driver()
                    self._show_toast(f"Profil '{prof.get('name', target_id)}' activé")
                except Exception as e:
                    self._show_toast(f"Erreur : {e}")

    def _on_new_profile_clicked(self, btn):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Créer un nouveau profil",
            body="Entrez le nom du nouveau profil de configuration.",
        )
        dialog.add_response("cancel", "Annuler")
        dialog.add_response("create", "Créer")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)

        entry = Gtk.Entry(placeholder_text="Nom du profil (ex: CS2 Compétitif)")
        dialog.set_extra_child(entry)

        def on_response(d, resp):
            if resp == "create":
                name = entry.get_text().strip()
                if name:
                    prof_id = name.lower().replace(" ", "_")
                    self.pm.create_profile(prof_id, name)
                    self.pm.switch_profile(prof_id, driver=self.driver)
                    self._sync_ui_from_driver()
                    self._show_toast(f"Profil '{name}' créé et activé")

        dialog.connect("response", on_response)
        dialog.present()

    def _on_import_profile_clicked(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Importer un profil SkillKorp K20")
        filter_json = Gtk.FileFilter()
        filter_json.set_name("Fichiers JSON de profil (*.json)")
        filter_json.add_pattern("*.json")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_json)
        dialog.set_filters(filters)

        def on_open_finish(d, result):
            try:
                gfile = d.open_finish(result)
                if gfile:
                    path = gfile.get_path()
                    prof_id = self.pm.import_profile(path)
                    self.pm.switch_profile(prof_id, driver=self.driver)
                    self._sync_ui_from_driver()
                    self._show_toast(f"Profil importé : {prof_id}")
            except Exception as e:
                self._show_toast(f"Erreur d'import : {e}")

        dialog.open(self, None, on_open_finish)

    def _on_auto_switch_toggled(self, row, param):
        self.pm.set_auto_switch_enabled(row.get_active())

    def _on_autostart_toggled(self, row, param):
        set_autostart(row.get_active())

    def _show_toast(self, message: str):
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)


class SkillkorpK20App(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.skillkorp.k20",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.connect("startup", self._on_startup)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = SkillkorpK20Window(self)
        win.present()

    def _on_startup(self, app):
        # Actions
        about_act = Gio.SimpleAction.new("about", None)
        about_act.connect("activate", self._on_about)
        self.add_action(about_act)

        reset_act = Gio.SimpleAction.new("factory_reset", None)
        reset_act.connect("activate", self._on_factory_reset)
        self.add_action(reset_act)

    def _on_about(self, action, param):
        dialog = Adw.AboutDialog(
            application_name="SkillKorp K20 Ultimate",
            application_icon="skillkorp-k20",
            developer_name="SkillKorp Linux Community",
            version="1.0.0",
            copyright="© 2026 SkillKorp Linux Project",
            license_type=Gtk.License.MIT_X11,
            website="https://github.com/ElMajor76/skillkorp-k20",
            issue_url="https://github.com/ElMajor76/skillkorp-k20/issues",
        )
        dialog.add_legal_section("Garantie et Compatibilité", None, Gtk.License.CUSTOM, "Pilote non officiel pour clavier de jeu SkillKorp K20 Ultimate.")
        dialog.present(self.props.active_window)

    def _on_factory_reset(self, action, param):
        win = self.props.active_window
        dialog = Adw.MessageDialog(
            transient_for=win,
            heading="Réinitialisation d'usine",
            body="Voulez-vous vraiment rétablir les réglages d'usine du clavier ? Tous vos profils matériels seront réinitialisés.",
        )
        dialog.add_response("cancel", "Annuler")
        dialog.add_response("reset", "Réinitialiser")
        dialog.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(d, resp):
            if resp == "reset" and win:
                win.driver.factory_reset()
                win._sync_ui_from_driver()
                win._show_toast("Clavier réinitialisé avec succès.")

        dialog.connect("response", on_response)
        dialog.present()


def main():
    app = SkillkorpK20App()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
