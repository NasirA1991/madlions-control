#!/usr/bin/env bash
# Remove Madlions Control. Saved profiles in ~/.local/share/madlions-control
# are intentionally left alone.
set -euo pipefail
umask 022

PREFIX="${PREFIX:-/usr}"
DESTDIR="${DESTDIR:-}"
USER_INSTALL=0
UDEV_ONLY=0
FORCE=0

usage() {
    cat <<'EOF'
Remove Madlions Control.

Usage:
  sudo ./uninstall.sh               Remove a system install, its package rule in
                                    /usr/lib/udev/rules.d/71-madlions.rules,
                                    and the admin rule in /etc/udev/rules.d.
  ./uninstall.sh --user             Remove a per-user install. Never touches
                                    /etc, even when run as root.
  sudo ./uninstall.sh --udev-only   Remove only
                                    /etc/udev/rules.d/71-madlions.rules.
  DESTDIR=/tmp/pkg PREFIX=/usr ./uninstall.sh
                                    Remove a staged/packaged install tree.

Options:
  --user          Remove files under ~/.local.
  --udev-only     Remove only the /etc rule (root required).
  --force         Override the package-ownership guard for a system uninstall.
  -h, --help      Show this help.

`--user` removes its own prefix rule under ~/.local but never /etc. A system
uninstall removes both the package rule and the admin rule. `71-atk-control.rules`
is never touched. Profiles under ~/.local/share/madlions-control are kept.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --user) USER_INSTALL=1 ;;
        --udev-only) UDEV_ONLY=1 ;;
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
    echo "error: --udev-only removes /etc directly and does not support DESTDIR" >&2
    exit 2
fi
if [[ $UDEV_ONLY -eq 1 && $EUID -ne 0 ]]; then
    echo "error: --udev-only requires root; run it with sudo" >&2
    exit 1
fi

if [[ $UDEV_ONLY -eq 1 ]]; then
    rm -f -- /etc/udev/rules.d/71-madlions.rules
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules 2>/dev/null || true
        udevadm trigger --subsystem-match=hidraw 2>/dev/null || true
    fi
    echo "Removed /etc/udev/rules.d/71-madlions.rules."
    exit 0
fi

if [[ $USER_INSTALL -eq 1 ]]; then
    PREFIX="${HOME}/.local"
fi
if [[ $USER_INSTALL -eq 0 && -z "$DESTDIR" && $EUID -ne 0 ]]; then
    echo "error: a system uninstall requires root; run sudo ./uninstall.sh" >&2
    echo "       or remove a user install with ./uninstall.sh --user" >&2
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
            echo "       Re-run with --force only if you intend to remove it." >&2
            return 1
        fi
    done
}

if [[ $USER_INSTALL -eq 0 && $UDEV_ONLY -eq 0 && -z "$DESTDIR" && $FORCE -eq 0 ]]; then
    if ! guard_package_ownership; then
        exit 1
    fi
fi

LIBDIR="${DESTDIR}${PREFIX}/lib/madlions-control"
BINDIR="${DESTDIR}${PREFIX}/bin"
APPDIR="${DESTDIR}${PREFIX}/share/applications"
ICONDIR="${DESTDIR}${PREFIX}/share/icons/hicolor"
METADIR="${DESTDIR}${PREFIX}/share/metainfo"
PREFIX_RULE="${DESTDIR}${PREFIX}/lib/udev/rules.d/71-madlions.rules"
ETC_RULE="${DESTDIR}/etc/udev/rules.d/71-madlions.rules"

rm -rf -- "$LIBDIR"
rm -f -- "$BINDIR/madlions-control" "$BINDIR/madlionsctl"
rm -f -- "$APPDIR/io.github.madlionscontrol.MadlionsControl.desktop"
rm -f -- "$METADIR/io.github.madlionscontrol.MadlionsControl.metainfo.xml"
rm -f -- "$ICONDIR/scalable/apps/io.github.madlionscontrol.MadlionsControl.svg"
rm -f -- "$ICONDIR/256x256/apps/io.github.madlionscontrol.MadlionsControl.png"
rm -f -- "$ICONDIR/512x512/apps/io.github.madlionscontrol.MadlionsControl.png"
rm -f -- "$PREFIX_RULE"
if [[ $USER_INSTALL -eq 0 ]]; then
    rm -f -- "$ETC_RULE"
fi

if [[ -z "$DESTDIR" ]]; then
    if command -v update-desktop-database >/dev/null; then
        update-desktop-database "$APPDIR" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache >/dev/null && [[ -e "$ICONDIR/icon-theme.cache" ]]; then
        gtk-update-icon-cache -q -t "$ICONDIR" 2>/dev/null || true
    fi
    if [[ $EUID -eq 0 ]]; then
        udevadm control --reload-rules 2>/dev/null || true
        udevadm trigger --subsystem-match=hidraw 2>/dev/null || true
    fi
fi

echo "Madlions Control removed. Profiles in ~/.local/share/madlions-control were kept."
