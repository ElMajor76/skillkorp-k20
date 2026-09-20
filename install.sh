#!/usr/bin/env bash
set -e

# ==============================================================================
# Script d'installation universel pour SkillKorp K20 Ultimate sous Linux
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"

detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO_ID="$ID"
        DISTRO_LIKE="${ID_LIKE:-$ID}"
    else
        DISTRO_ID="unknown"
        DISTRO_LIKE="unknown"
    fi
}

install_system_direct() {
    echo "⚙️  Installation directe dans le système (/usr)..."
    sudo mkdir -p /usr/share/skillkorp-k20
    sudo mkdir -p /usr/bin
    sudo mkdir -p /usr/lib/udev/rules.d
    sudo mkdir -p /usr/share/applications
    sudo mkdir -p /usr/share/icons/hicolor/256x256/apps

    sudo install -m 0755 "$SCRIPT_DIR/k20_driver.py" /usr/share/skillkorp-k20/k20_driver.py
    sudo install -m 0755 "$SCRIPT_DIR/profile_manager.py" /usr/share/skillkorp-k20/profile_manager.py
    sudo install -m 0755 "$SCRIPT_DIR/k20_gui.py" /usr/share/skillkorp-k20/k20_gui.py
    sudo install -m 0755 "$SCRIPT_DIR/k20_tray.py" /usr/share/skillkorp-k20/k20_tray.py
    sudo install -m 0755 "$SCRIPT_DIR/k20ctl" /usr/share/skillkorp-k20/k20ctl

    sudo cp -r "$SCRIPT_DIR/assets" /usr/share/skillkorp-k20/

    sudo ln -sf /usr/share/skillkorp-k20/k20ctl /usr/bin/k20ctl
    sudo ln -sf /usr/share/skillkorp-k20/k20_gui.py /usr/bin/k20-gui
    sudo ln -sf /usr/share/skillkorp-k20/k20_tray.py /usr/bin/k20-tray

    sudo install -m 0644 "$SCRIPT_DIR/udev/99-skillkorp-k20.rules" /usr/lib/udev/rules.d/99-skillkorp-k20.rules
    sudo install -m 0644 "$SCRIPT_DIR/io.github.skillkorp.k20.desktop" /usr/share/applications/io.github.skillkorp.k20.desktop
    sudo install -m 0644 "$SCRIPT_DIR/assets/skillkorp-k20.png" /usr/share/icons/hicolor/256x256/apps/skillkorp-k20.png

    sudo udevadm control --reload-rules 2>/dev/null || true
    sudo udevadm trigger --subsystem-match=hidraw 2>/dev/null || true
    sudo update-desktop-database /usr/share/applications 2>/dev/null || true
}

install_user_mode() {
    echo "👤 Installation en mode utilisateur (~/.local)..."
    mkdir -p "$HOME/.local/bin"
    mkdir -p "$HOME/.local/share/applications"
    mkdir -p "$HOME/.local/share/icons/hicolor/256x256/apps"

    ln -sf "$SCRIPT_DIR/k20ctl" "$HOME/.local/bin/k20ctl"
    ln -sf "$SCRIPT_DIR/k20_gui.py" "$HOME/.local/bin/k20-gui"
    ln -sf "$SCRIPT_DIR/k20_tray.py" "$HOME/.local/bin/k20-tray"
    cp -f "$SCRIPT_DIR/assets/skillkorp-k20.png" "$HOME/.local/share/icons/hicolor/256x256/apps/skillkorp-k20.png"
    cp -f "$SCRIPT_DIR/io.github.skillkorp.k20.desktop" "$HOME/.local/share/applications/"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

    echo ""
    echo "🔑 Pour que le clavier soit reconnu sans droits root, installation de la règle udev :"
    if [ "$EUID" -eq 0 ]; then
        cp -f "$SCRIPT_DIR/udev/99-skillkorp-k20.rules" /etc/udev/rules.d/
        udevadm control --reload-rules
        udevadm trigger --subsystem-match=hidraw
    else
        sudo cp -f "$SCRIPT_DIR/udev/99-skillkorp-k20.rules" /etc/udev/rules.d/
        sudo udevadm control --reload-rules
        sudo udevadm trigger --subsystem-match=hidraw
    fi
}

uninstall() {
    echo "🗑️  Désinstallation de SkillKorp K20 Ultimate..."
    
    # Check package managers first
    if command -v dnf >/dev/null 2>&1 && rpm -q skillkorp-k20 >/dev/null 2>&1; then
        sudo dnf remove -y skillkorp-k20
    elif command -v dpkg >/dev/null 2>&1 && dpkg -s skillkorp-k20 >/dev/null 2>&1; then
        sudo apt-get remove -y skillkorp-k20
    elif command -v pacman >/dev/null 2>&1 && pacman -Q skillkorp-k20 >/dev/null 2>&1; then
        sudo pacman -R skillkorp-k20
    fi

    # Clean system files
    sudo rm -rf /usr/share/skillkorp-k20
    sudo rm -f /usr/bin/k20ctl /usr/bin/k20-gui /usr/bin/k20-tray
    sudo rm -f /usr/lib/udev/rules.d/99-skillkorp-k20.rules /etc/udev/rules.d/99-skillkorp-k20.rules
    sudo rm -f /usr/share/applications/io.github.skillkorp.k20.desktop
    sudo rm -f /usr/share/icons/hicolor/256x256/apps/skillkorp-k20.png

    # Clean user files
    rm -f "$HOME/.local/bin/k20ctl" "$HOME/.local/bin/k20-gui" "$HOME/.local/bin/k20-tray"
    rm -f "$HOME/.local/share/applications/io.github.skillkorp.k20.desktop"
    rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/skillkorp-k20.png"
    rm -f "$HOME/.config/autostart/io.github.skillkorp.k20.tray.desktop"

    sudo udevadm control --reload-rules 2>/dev/null || true
    echo "✓ Désinstallation terminée."
    exit 0
}

# Parse options
MODE="auto"
for arg in "$@"; do
    case "$arg" in
        --user) MODE="user" ;;
        --system) MODE="system" ;;
        --package) MODE="package" ;;
        --uninstall) uninstall ;;
        -h|--help)
            echo "Usage: ./install.sh [OPTION]"
            echo ""
            echo "Options :"
            echo "  (par défaut)  Détecte automatiquement votre distribution et installe via le gestionnaire de paquets"
            echo "  --package     Force l'installation via le paquet natif (.rpm ou .deb)"
            echo "  --system      Installe directement dans /usr (système complet)"
            echo "  --user        Installe dans ~/.local/bin et installe la règle udev"
            echo "  --uninstall   Désinstalle complètement le pilote et ses fichiers"
            echo "  --help        Affiche cette aide"
            exit 0
            ;;
    esac
done

echo "============================================================"
echo "   Installation du pilote & GUI SkillKorp K20 Ultimate     "
echo "============================================================"

detect_distro
echo "🔍 Distribution détectée : $DISTRO_ID (famille: $DISTRO_LIKE)"

if [ "$MODE" = "user" ]; then
    install_user_mode
elif [ "$MODE" = "system" ]; then
    install_system_direct
else
    # Auto mode: try native package first
    INSTALLED_VIA_PKG=false

    # Make sure packages are built
    if [ ! -d "$DIST_DIR" ] || [ -z "$(ls -A "$DIST_DIR" 2>/dev/null)" ]; then
        echo "📦 Construction préalable des paquets d'installation..."
        python3 "$SCRIPT_DIR/packaging/build_packages.py" || true
    fi

    # Fedora / RHEL / CentOS / openSUSE
    if echo "$DISTRO_ID $DISTRO_LIKE" | grep -Eq 'fedora|rhel|centos|suse'; then
        RPM_PKG=$(find "$DIST_DIR" -name "skillkorp-k20-*.rpm" 2>/dev/null | head -n 1)
        if [ -n "$RPM_PKG" ] && command -v dnf >/dev/null 2>&1; then
            echo "📦 Installation du paquet RPM via DNF..."
            sudo dnf install -y "$RPM_PKG"
            INSTALLED_VIA_PKG=true
        fi
    fi

    # Debian / Ubuntu / Mint / Pop / Zorin
    if [ "$INSTALLED_VIA_PKG" = false ] && echo "$DISTRO_ID $DISTRO_LIKE" | grep -Eq 'debian|ubuntu|mint|pop'; then
        DEB_PKG=$(find "$DIST_DIR" -name "skillkorp-k20_*_all.deb" 2>/dev/null | head -n 1)
        if [ -n "$DEB_PKG" ] && command -v apt-get >/dev/null 2>&1; then
            echo "📦 Installation du paquet DEB via APT..."
            sudo apt-get install -y "$DEB_PKG"
            INSTALLED_VIA_PKG=true
        fi
    fi

    # Arch Linux / Manjaro
    if [ "$INSTALLED_VIA_PKG" = false ] && echo "$DISTRO_ID $DISTRO_LIKE" | grep -Eq 'arch'; then
        if command -v makepkg >/dev/null 2>&1; then
            echo "📦 Construction et installation via makepkg..."
            (cd "$SCRIPT_DIR/packaging/arch" && makepkg -si --noconfirm)
            INSTALLED_VIA_PKG=true
        fi
    fi

    # Fallback to direct system install if package installation was not performed
    if [ "$INSTALLED_VIA_PKG" = false ]; then
        install_system_direct
    fi
fi

echo ""
echo "============================================================"
echo "✓ Installation terminée avec succès !"
echo "============================================================"
echo "Vous pouvez dès à présent utiliser :"
echo "  • k20ctl status    (dans un terminal)"
echo "  • k20-gui          (ou via l'icône dans la liste d'applications)"
echo "  • k20-tray         (indicateur dans la barre des tâches / systray)"
echo "============================================================"
