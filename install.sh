#!/usr/bin/env bash
# Install Madlions Control.
#
#   sudo ./install.sh          system-wide (/usr), installs the package rule
#   ./install.sh --user        per-user (~/.local), no root
#   sudo ./install.sh --udev-only
#                              install only /etc/udev/rules.d/71-madlions.rules
#
# Packaging: DESTDIR=/tmp/pkg PREFIX=/usr ./install.sh --skip-deps
set -euo pipefail
umask 022

PREFIX="${PREFIX:-/usr}"
DESTDIR="${DESTDIR:-}"
USER_INSTALL=0
UDEV_ONLY=0
SKIP_DEPS=0
FORCE=0

usage() {
    cat <<'EOF'
Install Madlions Control.

Usage:
  sudo ./install.sh                 Install system-wide under /usr, including
                                    /usr/lib/udev/rules.d/71-madlions.rules.
  ./install.sh --user               Install under ~/.local; no root and no rule.
  sudo ./install.sh --udev-only     Install only /etc/udev/rules.d/71-madlions.rules.
  DESTDIR=/tmp/pkg PREFIX=/usr ./install.sh --skip-deps
                                    Stage an install for packaging.

Options:
  --user          Install for the current user under ~/.local.
  --udev-only     Install only /etc/udev/rules.d/71-madlions.rules (root only).
  --skip-deps     Do not check Python/GTK dependencies.
  --force         Override the package-ownership guard for a system install.
  -h, --help      Show this help.

After a --user install, run once:
  sudo ./install.sh --udev-only
Then unplug and replug the keyboard.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --user) USER_INSTALL=1 ;;
        --udev-only) UDEV_ONLY=1 ;;
        --skip-deps) SKIP_DEPS=1 ;;
        --force) FORCE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ $UDEV_ONLY -eq 1 && $USER_INSTALL -eq 1 ]]; then
    echo "error: --udev-only and --user cannot be used together" >&2
    exit 2
fi
if [[ $UDEV_ONLY -eq 1 && -n "$DESTDIR" ]]; then
    echo "error: --udev-only installs /etc directly and does not support DESTDIR" >&2
    exit 2
fi
if [[ $UDEV_ONLY -eq 1 && $EUID -ne 0 ]]; then
    echo "error: --udev-only requires root; run it with sudo" >&2
    exit 1
fi
if [[ $USER_INSTALL -eq 1 ]]; then
    PREFIX="${HOME}/.local"
    echo "Installing to ${PREFIX} (user)"
fi
if [[ $USER_INSTALL -eq 0 && -z "$DESTDIR" && $EUID -ne 0 ]]; then
    echo "error: a system install requires root; run sudo ./install.sh" >&2
    echo "       or install for your user with ./install.sh --user" >&2
    exit 1
fi

package_owner() {
    local path="$1" out pkg
    if command -v pacman >/dev/null 2>&1; then
        if out="$(pacman -Qqo "$path" 2>/dev/null)" && [[ -n "$out" ]]; then
            pkg="${out%%$'\n'*}"
            printf 'pacman\t%s\n' "$pkg"
            return 0
        fi
    fi
    if command -v dpkg >/dev/null 2>&1; then
        if out="$(dpkg -S "$path" 2>/dev/null)" && [[ -n "$out" ]]; then
            pkg="${out%%:*}"
            printf 'dpkg\t%s\n' "$pkg"
            return 0
        fi
    fi
    if command -v rpm >/dev/null 2>&1; then
        if out="$(rpm -qf "$path" 2>/dev/null)" && [[ -n "$out" && "$out" != *"not owned"* ]]; then
            pkg="${out%%$'\n'*}"
            printf 'rpm\t%s\n' "$pkg"
            return 0
        fi
    fi
    return 1
}

package_remove_hint() {
    local manager="$1" pkg="$2"
    case "$manager" in
        pacman) printf 'sudo pacman -Rns %s' "$pkg" ;;
        dpkg) printf 'sudo apt remove %s' "$pkg" ;;
        rpm) printf 'sudo rpm -e %s' "$pkg" ;;
        *) printf 'your package manager' ;;
    esac
}

guard_package_ownership() {
    local path owner manager pkg hint
    for path in "$PREFIX/lib/madlions-control" "$PREFIX/bin/madlions-control"; do
        if owner="$(package_owner "$path")"; then
            manager="${owner%%$'\t'*}"
            pkg="${owner#*$'\t'}"
            hint="$(package_remove_hint "$manager" "$pkg")"
            echo "error: $path is owned by package $pkg." >&2
            echo "       Use the package manager instead: $hint" >&2
            echo "       Re-run with --force only if you intend to overwrite it." >&2
            return 1
        fi
    done
}

if [[ $USER_INSTALL -eq 0 && $UDEV_ONLY -eq 0 && -z "$DESTDIR" && $FORCE -eq 0 ]]; then
    if ! guard_package_ownership; then
        exit 1
    fi
fi

# Work from the checkout even when invoked through an absolute path.
cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RULE_FILE="${PWD}/data/udev/71-madlions.rules"
if [[ ! -r "$RULE_FILE" ]]; then
    echo "error: missing udev rule: $RULE_FILE" >&2
    exit 1
fi

if [[ $UDEV_ONLY -eq 1 ]]; then
    install -Dm644 "$RULE_FILE" /etc/udev/rules.d/71-madlions.rules
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules
        udevadm trigger --subsystem-match=hidraw
    fi
    echo "Installed /etc/udev/rules.d/71-madlions.rules."
    echo "Unplug and replug the keyboard now."
    exit 0
fi

distro_family() {
    local family="unknown"
    local ids=()
    local id
    if [[ -r /etc/os-release ]]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        read -r -a ids <<< "${ID:-} ${ID_LIKE:-}"
        for id in "${ids[@]}"; do
            case "$id" in
                arch) family="arch"; break ;;
                debian|ubuntu) family="debian"; break ;;
                fedora) family="fedora"; break ;;
                opensuse*|suse*) family="opensuse"; break ;;
            esac
        done
    fi
    printf '%s\n' "$family"
}

print_dependency_help() {
    local family
    family="$(distro_family)"
    echo "Missing Python 3 or the GTK 4 / libadwaita Python bindings." >&2
    echo "Install the build/runtime dependencies for your distribution:" >&2
    case "$family" in
        arch)
            echo "  pacman -S --needed python-gobject gtk4 libadwaita python-cairo hicolor-icon-theme" >&2
            ;;
        debian)
            echo "  apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-cairo hicolor-icon-theme" >&2
            ;;
        fedora)
            echo "  dnf install python3-gobject gtk4 libadwaita python3-cairo hicolor-icon-theme" >&2
            ;;
        opensuse)
            echo "  zypper install python3-gobject python3-cairo typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 hicolor-icon-theme" >&2
            echo "  (openSUSE package names are unverified; adjust if zypper reports a missing package.)" >&2
            ;;
        *)
            echo "  python3, PyGObject (GTK 4, libadwaita, Pango, PangoCairo) and pycairo" >&2
            echo "  are required; use your distribution's package manager." >&2
            ;;
    esac
    echo "Alternatively, use the Flatpak build, which carries its own runtime." >&2
}

check_dependencies() {
    if [[ -n "$DESTDIR" || $SKIP_DEPS -eq 1 ]]; then
        return 0
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        print_dependency_help
        return 1
    fi
    if python3 - <<'PY' >/dev/null 2>&1
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango, PangoCairo
import cairo
PY
    then
        return 0
    fi
    print_dependency_help
    return 1
}

if ! check_dependencies; then
    exit 1
fi

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
chmod -R u=rwX,go=rX "$LIBDIR"

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
    install -m0644 "$RULE_FILE" "$UDEVDIR/"
fi

if [[ -z "$DESTDIR" ]]; then
    if command -v update-desktop-database >/dev/null; then
        update-desktop-database "$APPDIR" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache >/dev/null && [[ -e "$ICONDIR/icon-theme.cache" ]]; then
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
    echo "NOTE: the udev rule was not installed (it needs root). Run this once:"
    echo "  sudo ./install.sh --udev-only"
    echo "Then unplug and replug the keyboard."
fi
