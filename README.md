# Pilote & Gestionnaire Linux pour SkillKorp K20 Ultimate

Ce projet est une réimplémentation native sous Linux du logiciel Windows officiel (`ClavierK20Ultimate.exe`) pour le clavier mécanique gaming sans fil **SkillKorp K20 Ultimate** (format compact 75%, 84 touches, disposition AZERTY France).

---

## 🔍 Analyse & Rétro-ingénierie du Protocole

L'analyse binaire approfondie de l'exécutable (`ClavierK20Ultimate.exe`, frontend Electron React/MobX et backend gRPC `iot_driver.exe`) a révélé :
- **Architecture matérielle** : Solution SoC **Yichip YC3121** (carte mère **CX71D**) associée à un contrôleur USB/2.4GHz haute performance.
- **Identifiants USB** :
  - **Mode Sans Fil 2.4 GHz (Dongle USB)** : VID `0x3151`, PID `0x4011` ("KU SKK 2,4GHz")
  - **Mode Filaire (Câble USB-C)** : VID `0x3151`, PID `0x4015` ("KU SkillKorp")
- **Interface de communication** :
  - La configuration matérielle s'effectue via l'interface HID propriétaire (Interface 2, Usage Page `0xFFFF`, Usage `0x0002`) accessible via `/dev/hidraw*`.
  - Les commandes sont envoyées sous forme de **HID Feature Reports** de 64 octets (65 octets avec Report ID `0x00` sous Linux via l'ioctl `HIDIOCSFEATURE`).
  - L'interface 1 (Usage Page `0xFFFF`, Usage `0x0001`, Report ID `0x05`) transmet les notifications matérielles en temps réel (molette de volume, bascule d'éclairage).

### Commandes matérielles rétro-ingéniées :
1. **Éclairage RGB Principal (`FEA_CMD_SET_LEDPARAM = 0x04`)** :
   10 effets lumineux (Éteint, Fixe, Respiration, Onde, Ondulation, Pluie, Serpent, Touche active, Convergence, Personnalisé), vitesse (1 à 5), luminosité (0 à 4), direction de l'onde (gauche / droite) et couleur RGB 24 bits (R, G, B).
2. **Éclairage Latéral (`FEA_CMD_SET_SLEDPARAM = 0x08`)** :
   Gestion indépendante des diffuseurs lumineux gauche et droit (effets Arc-en-ciel, Onde, Respiration, Fixe, Éteint).
3. **Taux de rafraîchissement (`FEA_CMD_SET_REPORT = 0x01`)** :
   Codes matériels : 1000 Hz (`0x01`), 500 Hz (`0x02`), 250 Hz (`0x04`), 125 Hz (`0x08`).
4. **Temps d'anti-rebond (`FEA_CMD_SET_DEBOUNCE = 0x11`)** :
   Filtrage mécanique des commutateurs ajustable de 2 ms à 20 ms (8 ms par défaut).
5. **Gestion de l'alimentation & Veille (`FEA_CMD_SET_SLEEPTIME = 0x12`)** :
   Délai de veille légère (extinction LED, 10s à 600s, défaut 120s) et veille profonde (coupure radio sans fil, 10 min à 60 min, défaut 28 min).
6. **Options clavier (`FEA_CMD_SET_KBOPTION = 0x06`)** :
   Registre d'état gérant le verrouillage de la touche Windows (Win Lock), l'inversion des touches ZQSD et des flèches directionnelles, le mode système (Windows, macOS, iOS, Android) et le mode Gaming à faible latence.
7. **Remappage des touches (`FEA_CMD_SET_KEYMATRIX_SIMPLE = 0x13` & `0x15`)** :
   Remappage unitaire des touches standard (85 touches) et des combinaisons de la couche Fn (multimédia, souris, macros, raccourcis).
8. **Batterie & État de charge (`FEA_CMD_GET_BATTERY = 0x83`)** :
   Interrogation du niveau de charge et de l'alimentation USB.
9. **Réinitialisation d'usine (`FEA_CMD_SET_RESERT = 0x0A`)** :
   Restauration complète des paramètres du microprogramme.

---

## 🛠️ Outils Disponibles

### 1. Utilitaire en Ligne de Commande : `k20ctl`

Accessible directement dans votre terminal :

```bash
# État complet du clavier et de la batterie
k20ctl status

# Sortie au format JSON pour scripts et intégrations
k20ctl status --json

# Niveau de batterie
k20ctl battery

# Configuration du rétroéclairage RGB
k20ctl rgb --mode wave --speed 3 --brightness 4
k20ctl rgb --mode static --color "#FF0055"

# Bandes LED latérales
k20ctl side-rgb --mode rainbow --brightness 4

# Fréquence de scrutation (1000, 500, 250 ou 125 Hz)
k20ctl polling-rate 1000

# Anti-rebond (debounce)
k20ctl debounce 4

# Délais de veille
k20ctl sleep --light 120 --deep 1800

# Verrouillage touche Windows
k20ctl win-lock on
k20ctl win-lock off
k20ctl win-lock toggle

# Inversion ZQSD / Flèches
k20ctl wasd-swap toggle

# Mode Gaming
k20ctl gaming-mode on

# Gestion des profils
k20ctl profile list
k20ctl profile set gaming
k20ctl profile new cs2 --copy-from gaming
k20ctl profile export gaming ~/k20_gaming.json
k20ctl profile import ~/k20_gaming.json
```

### 2. Interface Graphique Moderne : `k20-gui`

Application native GTK 4 / Libadwaita respectant les standards visuels GNOME :
- **Onglet Éclairage RGB** : Sélection visuelle des 10 effets, curseurs de vitesse et de luminosité, sélecteur de couleur hexadécimal et palette rapide. Contrôle dédié des bandes LED latérales.
- **Onglet Performance & Veille** : Choix du polling rate (125 à 1000 Hz), réglage d'anti-rebond (2 à 20 ms) et curseurs de mise en veille matérielle.
- **Onglet Clavier** : Interrupteurs pour le verrouillage Windows, l'inversion ZQSD, le mode système et le mode Gaming. Rendu graphique du clavier 75% avec sélecteur de remappage des touches.
- **Onglet Profils** : Gestion des profils enregistrés (Défaut, Gaming, Bureautique, Éco), import/export JSON, assignation d'applications actives pour la bascule automatique et option de démarrage avec la session.

### 3. Indicateur de Barre des Tâches : `k20-tray`

Applet systray discrète compatible avec GNOME (via AppIndicator extension), KDE Plasma, XFCE, Sway et Hyprland :
- Affichage du pourcentage de batterie avec icône dynamique et indicateur de charge.
- Notifications de batterie faible (< 20%, < 10%).
- Menu contextuel rapide pour changer d'effet RGB, de profil ou basculer le verrouillage Windows sans ouvrir la fenêtre principale.
- Démon intégré de détection de l'application active pour la bascule automatique de profils.

---

## 📦 Installation

### Installation Rapide Automatique

Exécutez simplement le script `install.sh` :

```bash
chmod +x install.sh
./install.sh
```

Le script détecte automatiquement votre distribution Linux et installe le paquet natif (.rpm sur Fedora, .deb sur Ubuntu/Debian/Mint, ou PKGBUILD sur Arch Linux).

### Options d'installation

```bash
# Installation en mode utilisateur sans droits root (dans ~/.local/bin)
./install.sh --user

# Installation système directe dans /usr
./install.sh --system

# Désinstallation complète
./install.sh --uninstall
```

### Règle udev

Pour permettre la configuration sans droits `sudo`, une règle udev est installée dans `/etc/udev/rules.d/99-skillkorp-k20.rules` :

```udev
KERNEL=="hidraw*", ATTRS{idVendor}=="3151", ATTRS{idProduct}=="4011", MODE="0660", TAG+="uaccess"
KERNEL=="hidraw*", ATTRS{idVendor}=="3151", ATTRS{idProduct}=="4015", MODE="0660", TAG+="uaccess"
```

Rechargez ensuite les règles udev :
```bash
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=hidraw
```

---

## 🧪 Tests Unitaires

La suite de tests unitaires complète basée sur `pytest` valide les calculs d'ioctl, les formats de paquets et la persistance des données :

```bash
python3 -m pytest tests/test_driver.py -v
```

---

## 📄 Licence

Ce projet est distribué sous licence MIT. Consultez le fichier [LICENSE](file:///home/nplacide/Projects/skillkorp-k20/LICENSE) pour plus d'informations.
SkillKorp est une marque déposée de ses propriétaires respectifs. Ce logiciel tiers indépendant n'est pas affilié à SkillKorp.
