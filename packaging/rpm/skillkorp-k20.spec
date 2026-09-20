%{!?_udevrulesdir: %global _udevrulesdir %{_prefix}/lib/udev/rules.d}

Name:           skillkorp-k20
Version:        1.0.0
Release:        1%{?dist}
Summary:        Pilote et interface graphique Linux pour clavier SkillKorp K20 Ultimate
License:        MIT
URL:            https://github.com/ElMajor76/skillkorp-k20
BuildArch:      noarch

Requires:       python3
Requires:       python3-gobject
Requires:       libadwaita
Requires:       systemd-udev
Recommends:     libayatana-appindicator-gtk3
Recommends:     libappindicator-gtk3

%description
Pilote natif sous Linux, utilitaire CLI (k20ctl), application GTK 4 / Libadwaita
(k20-gui) et applet systray (k20-tray) pour le clavier gaming compact 75%
SkillKorp K20 Ultimate (SoC Yichip YC3121 et carte CX71D).

%prep
# Pas d'étape de compilation requise

%build
# Scripts Python, rien à compiler

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}%{_datadir}/skillkorp-k20
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_udevrulesdir}
mkdir -p %{buildroot}%{_datadir}/applications
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/256x256/apps

# Fichiers de l'application
install -m 0755 %{_sourcedir}/k20_driver.py %{buildroot}%{_datadir}/skillkorp-k20/k20_driver.py
install -m 0755 %{_sourcedir}/profile_manager.py %{buildroot}%{_datadir}/skillkorp-k20/profile_manager.py
install -m 0755 %{_sourcedir}/k20_gui.py %{buildroot}%{_datadir}/skillkorp-k20/k20_gui.py
install -m 0755 %{_sourcedir}/k20_tray.py %{buildroot}%{_datadir}/skillkorp-k20/k20_tray.py
install -m 0755 %{_sourcedir}/k20ctl %{buildroot}%{_datadir}/skillkorp-k20/k20ctl
cp -r %{_sourcedir}/assets %{buildroot}%{_datadir}/skillkorp-k20/

# Liens symboliques dans /usr/bin
ln -s %{_datadir}/skillkorp-k20/k20ctl %{buildroot}%{_bindir}/k20ctl
ln -s %{_datadir}/skillkorp-k20/k20_gui.py %{buildroot}%{_bindir}/k20-gui
ln -s %{_datadir}/skillkorp-k20/k20_tray.py %{buildroot}%{_bindir}/k20-tray

# Règle udev, lanceur .desktop et icône
install -m 0644 %{_sourcedir}/udev/99-skillkorp-k20.rules %{buildroot}%{_udevrulesdir}/99-skillkorp-k20.rules
install -m 0644 %{_sourcedir}/io.github.skillkorp.k20.desktop %{buildroot}%{_datadir}/applications/io.github.skillkorp.k20.desktop
install -m 0644 %{_sourcedir}/assets/skillkorp-k20.png %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/skillkorp-k20.png

%post
udevadm control --reload-rules >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=hidraw >/dev/null 2>&1 || :
update-desktop-database %{_datadir}/applications >/dev/null 2>&1 || :

%postun
udevadm control --reload-rules >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=hidraw >/dev/null 2>&1 || :
update-desktop-database %{_datadir}/applications >/dev/null 2>&1 || :

%files
%{_datadir}/skillkorp-k20
%{_bindir}/k20ctl
%{_bindir}/k20-gui
%{_bindir}/k20-tray
%{_udevrulesdir}/99-skillkorp-k20.rules
%{_datadir}/applications/io.github.skillkorp.k20.desktop
%{_datadir}/icons/hicolor/256x256/apps/skillkorp-k20.png

%changelog
* Sun Sep 20 2026 nplacide <nplacide95@gmail.com> - 1.0.0-1
- Version initiale avec support complet sans fil 2.4GHz et filaire USB-C
- Pilote matériel Linux natif via rapports Feature HID (SoC YC3121)
- Utilitaire CLI k20ctl, interface GTK4/Libadwaita k20-gui et applet systray k20-tray
