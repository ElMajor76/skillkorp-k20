# Journal des modifications (Changelog) - SkillKorp K20 Ultimate

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.
Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/) et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

---

## [1.0.0] - 2026-09-20

### Ajouté
- **Rétro-ingénierie complète de `ClavierK20Ultimate.exe`** :
  - Découverte de l'architecture matérielle SoC Yichip YC3121 et carte CX71D.
  - Détection automatique USB sans fil 2.4 GHz (`3151:4011`) et filaire USB-C (`3151:4015`).
  - Protocole HID Feature Reports (64 octets / 65 octets avec Report ID 0x00) sur l'interface 2 (`0xFFFF:0x0002`).
- **Pilote matériel Linux natif (`k20_driver.py`)** :
  - Éclairage RGB complet (10 effets lumineux, vitesse 1-5, luminosité 0-4, direction, palette et couleur personnalisée).
  - Éclairage latéral indépendant (bandes LED gauche et droite).
  - Taux de rafraîchissement (125 Hz, 250 Hz, 500 Hz, 1000 Hz).
  - Filtrage mécanique anti-rebond (debounce 2 ms à 20 ms).
  - Gestion des délais de mise en veille matérielle (veille légère et veille profonde).
  - Options matérielles intégrées : Verrouillage touche Windows, Inversion ZQSD / Flèches, Mode Système (Win/Mac/iOS/Android), Mode Gaming.
  - Remappage unitaire des touches standard et de la couche Fn (disposition compacte 75% AZERTY France).
  - Interrogation en temps réel de la batterie et de l'état de charge.
  - Réinitialisation d'usine aux paramètres par défaut.
- **Gestionnaire multi-profils (`profile_manager.py`)** :
  - Profils par défaut : "Par défaut", "Gaming / Compétition", "Bureautique / Travail", "Nuit & Économie d'énergie".
  - Détection dynamique de la fenêtre active pour la bascule automatique de profils (X11 avec `xdotool`/`xprop`, Wayland avec `hyprctl` et `swaymsg`).
  - Importation et exportation de profils au format JSON avec validation stricte.
- **Utilitaire en ligne de commande (`k20ctl`)** :
  - Commandes `status`, `battery`, `rgb`, `side-rgb`, `polling-rate`, `debounce`, `sleep`, `win-lock`, `wasd-swap`, `os-mode`, `gaming-mode`, `remap`, `reset`, `profile`, `daemon`.
  - Support complet du format `--json` pour l'intégration et les scripts.
- **Application graphique GTK 4 / Libadwaita (`k20-gui`)** :
  - Interface moderne intégrant les directives de conception GNOME.
  - Onglet Éclairage RGB avec sélecteurs d'effets, curseurs et palette de couleurs.
  - Onglet Performance & Veille avec réglages fins et alertes d'autonomie.
  - Onglet Clavier avec commutateurs matériels et rendu graphique du clavier 75% AZERTY.
  - Onglet Profils avec gestion complète et règles d'automatisation.
  - Pillule d'état de connexion et indicateur dynamique de batterie dans la barre de titre.
- **Indicateur de barre des tâches (`k20_tray.py`)** :
  - Applet systray (AyatanaAppIndicator3 / AppIndicator3).
  - Affichage en temps réel du pourcentage et de l'icône de batterie.
  - Notifications système pour batterie faible (< 20%, < 10%) et connexion du périphérique.
  - Menu rapide pour changer de profil, d'effet RGB ou basculer le verrouillage Windows.
- **Intégration & Packaging Linux** :
  - Script d'installation universel `install.sh` avec détection automatique de distribution.
  - Règle udev (`99-skillkorp-k20.rules`) avec permissions non-root (`uaccess`).
  - Fichier de lanceur de bureau (`io.github.skillkorp.k20.desktop`).
  - Paquets d'installation natifs générés par `build_packages.py` : RPM (Fedora), DEB (Debian/Ubuntu), PKGBUILD (Arch Linux) et archive source.
  - Suite de tests unitaires `pytest` (`tests/test_driver.py`).
