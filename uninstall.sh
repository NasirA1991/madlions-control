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

echo "Madlions Control removed. Profiles in ~/.local/share/madlions-control were kept."
