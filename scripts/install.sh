#!/bin/sh
# Installiert die Quadlet-Units und die Konfiguration für den aktuellen Benutzer
# (rootless) und lädt systemd neu. Startet die Dienste nicht.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DIR="$HOME/.config/containers/systemd"
CONF_DIR="$HOME/.config/weiss"

mkdir -p "$UNIT_DIR" "$CONF_DIR"
cp "$ROOT"/quadlet/*.container "$ROOT"/quadlet/*.network "$ROOT"/quadlet/*.volume "$UNIT_DIR"/

# Vorhandene Konfiguration nicht überschreiben.
[ -f "$CONF_DIR/weiss.env" ] || cp "$ROOT/quadlet/weiss.env.example" "$CONF_DIR/weiss.env"
[ -f "$CONF_DIR/roles.toml" ] || cp "$ROOT/roles.toml" "$CONF_DIR/roles.toml"

systemctl --user daemon-reload
echo "Units installiert in $UNIT_DIR, Konfiguration in $CONF_DIR."
echo "Nächste Schritte: scripts/build-images.sh && systemctl --user enable --now weiss.service"
