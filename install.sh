#!/usr/bin/env bash
# Install Madlions Control.
#
#   sudo ./install.sh          # system-wide (/usr), installs the udev rule
#   ./install.sh --user        # per-user (~/.local), no root
#
# Packaging: DESTDIR=/tmp/pkg PREFIX=/usr ./install.sh
set -euo pipefail

PREFIX="${PREFIX:-/usr}"
DESTDIR="${DESTDIR:-}"
USER_INSTALL=0
for arg in "$@"; do
    case "$arg" in
        --user) USER_INSTALL=1 ;;
        -h|--help)
            sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

if [[ $USER_INSTALL -eq 1 ]]; then
    PREFIX="${HOME}/.local"
    echo "Installing to ${PREFIX} (user)"
fi

# Work from the checkout even when invoked through an absolute path.
cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

LIBDIR="${DESTDIR}${PREFIX}/lib/madlions-control"
BINDIR="${DESTDIR}${PREFIX}/bin"
APPDIR="${DESTDIR}${PREFIX}/share/applications"
ICONDIR="${DESTDIR}${PREFIX}/share/icons/hicolor"
METADIR="${DESTDIR}${PREFIX}/share/metainfo"
UDEVDIR="${DESTDIR}${PREFIX}/lib/udev/rules.d"

install -d "$LIBDIR" "$BINDIR" "$APPDIR" "$ICONDIR/scalable/apps" \
    "$ICONDIR/256x256/apps" "$ICONDIR/512x512/apps" "$METADIR"
rm -rf "$LIBDIR/madlions_control" "$LIBDIR/data"
cp -r madlions_control "$LIBDIR/madlions_control"
cp -r data "$LIBDIR/data"
find "$LIBDIR" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$LIBDIR" -name '*.pyc' -delete
# sudo commonly resets umask to 077; make the installed tree readable.
find "$LIBDIR" -type d -exec chmod 0755 {} +
find "$LIBDIR" -type f -exec chmod 0644 {} +

cat > "$BINDIR/madlions-control" <<LAUNCHER
#!/usr/bin/env python3
import sys
sys.path.insert(0, "${PREFIX}/lib/madlions-control")
from madlions_control.app import main
sys.exit(main())
LAUNCHER
chmod 0755 "$BINDIR/madlions-control"

cat > "$BINDIR/madlionsctl" <<LAUNCHER
#!/usr/bin/env python3
import sys
sys.path.insert(0, "${PREFIX}/lib/madlions-control")
from madlions_control.cli import main
sys.exit(main())
LAUNCHER
chmod 0755 "$BINDIR/madlionsctl"

install -m0644 data/icons/hicolor/scalable/apps/io.github.madlionscontrol.MadlionsControl.svg \
    "$ICONDIR/scalable/apps/"
install -m0644 data/icons/hicolor/256x256/apps/io.github.madlionscontrol.MadlionsControl.png \
    "$ICONDIR/256x256/apps/"
install -m0644 data/icons/hicolor/512x512/apps/io.github.madlionscontrol.MadlionsControl.png \
    "$ICONDIR/512x512/apps/"
install -m0644 data/io.github.madlionscontrol.MadlionsControl.desktop "$APPDIR/"
install -m0644 data/metainfo/io.github.madlionscontrol.MadlionsControl.metainfo.xml "$METADIR/"

if [[ $USER_INSTALL -eq 0 ]]; then
    install -d "$UDEVDIR"
    install -m0644 data/udev/71-madlions.rules "$UDEVDIR/"
fi

if [[ -z "$DESTDIR" ]]; then
    if command -v update-desktop-database >/dev/null; then
        update-desktop-database "$APPDIR" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache >/dev/null; then
        gtk-update-icon-cache -q -t "$ICONDIR" 2>/dev/null || true
    fi
    if [[ $USER_INSTALL -eq 0 && $EUID -eq 0 ]]; then
        udevadm control --reload-rules 2>/dev/null || true
        udevadm trigger --subsystem-match=hidraw 2>/dev/null || true
    fi
fi

echo
echo "Madlions Control installed."
echo "  run:  madlions-control"
echo "  test: madlions-control --demo"
echo "  CLI:  madlionsctl status"
if [[ $USER_INSTALL -eq 1 ]]; then
    echo
    echo "NOTE: the udev rule was not installed (needs root). If the app reports"
    echo "'permission denied', run:"
    echo "  sudo install -m644 data/udev/71-madlions.rules /usr/lib/udev/rules.d/"
    echo "  sudo udevadm control --reload-rules && sudo udevadm trigger"
fi
