#!/usr/bin/env bash
# Remove Madlions Control. Saved profiles in ~/.local/share/madlions-control
# are intentionally left alone.
set -euo pipefail

PREFIX="${PREFIX:-/usr}"
DESTDIR="${DESTDIR:-}"
if [[ "${1:-}" == "--user" ]]; then
    PREFIX="${HOME}/.local"
fi

rm -rf "${DESTDIR}${PREFIX}/lib/madlions-control"
rm -f "${DESTDIR}${PREFIX}/bin/madlions-control" "${DESTDIR}${PREFIX}/bin/madlionsctl"
rm -f "${DESTDIR}${PREFIX}/share/applications/io.github.madlionscontrol.MadlionsControl.desktop"
rm -f "${DESTDIR}${PREFIX}/share/metainfo/io.github.madlionscontrol.MadlionsControl.metainfo.xml"
rm -f "${DESTDIR}${PREFIX}/share/icons/hicolor/scalable/apps/io.github.madlionscontrol.MadlionsControl.svg"
rm -f "${DESTDIR}${PREFIX}/share/icons/hicolor/256x256/apps/io.github.madlionscontrol.MadlionsControl.png"
rm -f "${DESTDIR}${PREFIX}/share/icons/hicolor/512x512/apps/io.github.madlionscontrol.MadlionsControl.png"
rm -f "${DESTDIR}${PREFIX}/lib/udev/rules.d/71-madlions.rules"

if [[ -z "$DESTDIR" ]]; then
    APPDIR="${PREFIX}/share/applications"
    ICONDIR="${PREFIX}/share/icons/hicolor"
    if command -v update-desktop-database >/dev/null; then
        update-desktop-database "$APPDIR" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache >/dev/null; then
        gtk-update-icon-cache -q -t "$ICONDIR" 2>/dev/null || true
    fi
    if [[ $EUID -eq 0 ]]; then
        udevadm control --reload-rules 2>/dev/null || true
        udevadm trigger --subsystem-match=hidraw 2>/dev/null || true
    fi
fi

echo "Madlions Control removed. Profiles in ~/.local/share/madlions-control were kept."
