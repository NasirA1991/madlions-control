#!/usr/bin/env bash
# get.sh - one-line installer for Madlions Control.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/NasirA1991/madlions-control/main/get.sh | bash
#   curl -fsSL ... | bash -s -- --yes
#
# This script installs a released build, never an arbitrary branch. Every
# downloaded release asset is checked against the release's SHA256SUMS before
# it is extracted or executed.
set -euo pipefail
umask 022

REPO="NasirA1991/madlions-control"
APP="madlions-control"
AUR_PACKAGE="madlions-control"
FLATPAK_ID="io.github.madlionscontrol.MadlionsControl"
API_URL="https://api.github.com/repos/${REPO}/releases/latest"
RELEASE_BASE="https://github.com/${REPO}/releases/download"
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/${APP}"
STATE_FILE="${STATE_DIR}/get-sh.state"

USER_INSTALL=0
METHOD=""
VERSION=""
TAG=""
YES=0
DRY_RUN=0
UNINSTALL=0
SHOW_HELP=0

OS_ID=""
OS_LIKE=""
OS_NAME=""
ARCH=""
DOWNLOADER=""
AUR_HELPER=""
AUR_MODE=""
BASE=""
TMP_DIR=""
SRC_DIR=""
ASSET_SOURCE=""
ASSET_FLATPAK=""

STATE_METHOD=""
STATE_VERSION=""
STATE_USER="0"
STATE_SCOPE=""

say() {
    printf '%s\n' "$*"
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

cleanup() {
    if [[ -n ${TMP_DIR:-} && -d ${TMP_DIR} ]]; then
        rm -rf -- "$TMP_DIR"
    fi
}

usage() {
    cat <<'USAGE'
Madlions Control one-line installer.

Usage:
  get.sh [options]

Options:
  --user              Install for the current user where the method supports it.
  --method METHOD     Force aur, flatpak, or source (default: auto-detect).
  --version VERSION   Install a specific release, for example v0.4.0.
  --yes               Do not ask for confirmation.
  --dry-run           Print the plan and commands without running them.
  --uninstall         Undo the install recorded in the get.sh state file.
  -h, --help          Show this help.

The default method is AUR on Arch-based systems (helper, then makepkg, then
manual instructions), Flatpak on other systems when available, and the source
tarball otherwise. Flatpak and source installs use the release's install.sh and
its --udev-only mode for the host udev rule.

Testing only: GET_SH_BASE_URL overrides the release download base URL. It must
point at a directory laid out as <base>/vX.Y.Z/<asset> and requires --version.
USAGE
}

parse_args() {
    while (( $# > 0 )); do
        case "$1" in
            --user)
                USER_INSTALL=1
                ;;
            --method)
                if (( $# < 2 )); then
                    die "--method needs a value: aur, flatpak, or source"
                fi
                METHOD=$2
                shift
                ;;
            --method=*)
                METHOD=${1#*=}
                ;;
            --version)
                if (( $# < 2 )); then
                    die "--version needs a value such as v0.4.0"
                fi
                VERSION=$2
                shift
                ;;
            --version=*)
                VERSION=${1#*=}
                ;;
            --yes|-y)
                YES=1
                ;;
            --dry-run)
                DRY_RUN=1
                ;;
            --uninstall)
                UNINSTALL=1
                ;;
            -h|--help)
                SHOW_HELP=1
                ;;
            *)
                die "unknown option: $1 (use --help)"
                ;;
        esac
        shift
    done

    case "$METHOD" in
        ""|aur|flatpak|source) ;;
        *) die "--method must be aur, flatpak, or source" ;;
    esac

    if (( UNINSTALL )); then
        if [[ -n $METHOD || -n $VERSION ]]; then
            die "--uninstall uses the recorded method and version; do not pass --method or --version"
        fi
    fi
}

normalize_version() {
    if [[ -z $VERSION || $VERSION == latest ]]; then
        VERSION=""
        return 0
    fi
    if [[ $VERSION == v* ]]; then
        VERSION=${VERSION#v}
    fi
    if [[ ! $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z]+)*$ ]]; then
        die "invalid --version '$VERSION'; use a tag such as v0.4.0"
    fi
    TAG="v${VERSION}"
}

read_os_release() {
    local file=/etc/os-release
    if [[ -r $file ]]; then
        OS_ID=$(sed -n 's/^ID=//p' "$file" | head -n 1 | tr -d '"')
        OS_LIKE=$(sed -n 's/^ID_LIKE=//p' "$file" | head -n 1 | tr -d '"')
        OS_NAME=$(sed -n 's/^PRETTY_NAME=//p' "$file" | head -n 1 | tr -d '"')
    fi
    OS_ID=${OS_ID:-unknown}
    OS_NAME=${OS_NAME:-$OS_ID}
}

detect_os() {
    read_os_release
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64|amd64)
            ARCH=x86_64
            ;;
        *)
            die "unsupported architecture '$ARCH'; releases are published for x86_64 only. Use the source install from https://github.com/${REPO}"
            ;;
    esac
}

is_arch() {
    case " ${OS_ID} ${OS_LIKE} " in
        *" arch "*) return 0 ;;
        *) return 1 ;;
    esac
}

package_hint() {
    local packages=$1
    case " ${OS_ID} ${OS_LIKE} " in
        *" arch "*) printf 'sudo pacman -S --needed %s\n' "$packages" ;;
        *" debian "*|*" ubuntu "*) printf 'sudo apt install %s\n' "$packages" ;;
        *" fedora "*|*" rhel "*) printf 'sudo dnf install %s\n' "$packages" ;;
        *" suse "*|*" opensuse "*) printf 'sudo zypper install %s\n' "$packages" ;;
        *" alpine "*) printf 'sudo apk add %s\n' "$packages" ;;
        *) printf 'Install %s with your package manager.\n' "$packages" ;;
    esac
}

detect_downloader() {
    if command -v curl >/dev/null 2>&1; then
        DOWNLOADER=curl
    elif command -v wget >/dev/null 2>&1; then
        DOWNLOADER=wget
    fi
}

require_tools() {
    local missing=0
    if [[ -z $DOWNLOADER ]]; then
        printf 'error: curl or wget is required.\n' >&2
        package_hint "curl tar coreutils" >&2
        missing=1
    fi
    if ! command -v tar >/dev/null 2>&1; then
        printf 'error: tar is required.\n' >&2
        package_hint "tar" >&2
        missing=1
    fi
    if ! command -v sha256sum >/dev/null 2>&1; then
        printf 'error: sha256sum is required.\n' >&2
        package_hint "coreutils" >&2
        missing=1
    fi
    if (( missing )); then
        exit 1
    fi
}

require_sudo() {
    if ! command -v sudo >/dev/null 2>&1; then
        die "sudo is required for this step; install sudo, then run get.sh again"
    fi
}

require_flatpak() {
    if ! command -v flatpak >/dev/null 2>&1; then
        die "Flatpak is not installed; install flatpak or use --method source"
    fi
}

detect_aur_helper() {
    local helper
    for helper in paru yay; do
        if command -v "$helper" >/dev/null 2>&1; then
            AUR_HELPER=$helper
            return 0
        fi
    done
    return 1
}

aur_makepkg_ready() {
    local tool
    for tool in git makepkg gcc make fakeroot; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            return 1
        fi
    done
    return 0
}

choose_method() {
    if [[ -n $METHOD ]]; then
        case "$METHOD" in
            aur)
                is_arch || die "--method aur is only for Arch-based systems"
                if (( USER_INSTALL )); then
                    die "AUR packages install system-wide; use --method source --user for a user install"
                fi
                if [[ -n $VERSION ]]; then
                    die "--version is not supported with the AUR method; use --method source or --method flatpak"
                fi
                if detect_aur_helper; then
                    AUR_MODE=helper
                elif aur_makepkg_ready; then
                    AUR_MODE=makepkg
                else
                    AUR_MODE=manual
                fi
                ;;
            flatpak)
                require_flatpak
                ;;
            source)
                ;;
            *)
                die "unknown method '$METHOD'"
                ;;
        esac
        return 0
    fi

    if is_arch && (( USER_INSTALL == 0 )); then
        if detect_aur_helper; then
            METHOD=aur
            AUR_MODE=helper
        elif aur_makepkg_ready; then
            METHOD=aur
            AUR_MODE=makepkg
        else
            METHOD=aur
            AUR_MODE=manual
        fi
    elif command -v flatpak >/dev/null 2>&1; then
        METHOD=flatpak
    else
        METHOD=source
    fi
}

method_label() {
    case "$METHOD" in
        aur)
            case "$AUR_MODE" in
                helper) printf 'AUR (%s)' "$AUR_HELPER" ;;
                makepkg) printf 'AUR (makepkg)' ;;
                *) printf 'AUR (manual)' ;;
            esac
            ;;
        flatpak) printf 'Flatpak' ;;
        source) printf 'source tarball' ;;
        *) printf '%s' "$METHOD" ;;
    esac
}

package_owner() {
    local bin owner
    bin=$(command -v "$APP" 2>/dev/null || true)
    [[ -n $bin ]] || return 1

    if command -v pacman >/dev/null 2>&1; then
        owner=$(pacman -Qqo "$bin" 2>/dev/null | head -n 1 || true)
        if [[ -n $owner ]]; then
            OWNER_MANAGER=pacman
            OWNER_PACKAGE=$owner
            return 0
        fi
    fi
    if command -v dpkg >/dev/null 2>&1; then
        owner=$(dpkg -S "$bin" 2>/dev/null | head -n 1 | cut -d: -f1 || true)
        if [[ -n $owner ]]; then
            OWNER_MANAGER=dpkg
            OWNER_PACKAGE=$owner
            return 0
        fi
    fi
    if command -v rpm >/dev/null 2>&1; then
        owner=$(rpm -qf "$bin" 2>/dev/null | head -n 1 || true)
        if [[ -n $owner && $owner != *"not owned"* ]]; then
            OWNER_MANAGER=rpm
            OWNER_PACKAGE=$owner
            return 0
        fi
    fi
    return 1
}

package_remove_hint() {
    case "$OWNER_MANAGER" in
        pacman) printf 'sudo pacman -Rns %s\n' "$OWNER_PACKAGE" ;;
        dpkg) printf 'sudo apt remove %s\n' "$OWNER_PACKAGE" ;;
        rpm) printf 'sudo rpm -e %s\n' "$OWNER_PACKAGE" ;;
        *) printf 'Remove %s with your package manager.\n' "$OWNER_PACKAGE" ;;
    esac
}

check_existing_install() {
    if ! package_owner; then
        return 0
    fi

    say "Madlions Control is already installed by $OWNER_MANAGER: $OWNER_PACKAGE."
    if [[ $METHOD == aur ]] && is_arch && detect_aur_helper; then
        if (( DRY_RUN )); then
            say "Would upgrade through $AUR_HELPER: $AUR_HELPER -S --needed $AUR_PACKAGE"
            exit 0
        fi
        if (( YES )) || confirm "Upgrade it through $AUR_HELPER now?"; then
            run "$AUR_HELPER" -S --needed "$AUR_PACKAGE"
            exit 0
        fi
    fi
    say "Use the package manager to upgrade or remove it:"
    package_remove_hint
    die "refusing to install a second copy"
}

confirm() {
    local prompt=$1
    local answer=""

    if (( YES )); then
        return 0
    fi
    if [[ ! -r /dev/tty ]]; then
        die "no terminal available for confirmation; re-run with --yes"
    fi
    printf '%s [y/N] ' "$prompt" >/dev/tty
    IFS= read -r answer </dev/tty || answer=""
    case "$answer" in
        y|Y|yes|YES) return 0 ;;
        *) die "aborted by user" ;;
    esac
}

print_manual_aur() {
    cat <<'EOF'
No AUR helper and no complete base-devel toolchain were found.
Install it with your package manager if needed, then run:

  git clone https://aur.archlinux.org/madlions-control.git
  cd madlions-control
  makepkg -si

The package installs the udev rule itself.
EOF
}

plan_install() {
    local label
    label=$(method_label)

    printf 'Detected: %s, %s.\n' "$OS_NAME" "$ARCH"
    printf 'Method: %s.\n' "$label"
    if (( USER_INSTALL )); then
        printf 'Scope: current user (host udev rule still uses sudo).\n'
    fi
    if [[ -n $TAG ]]; then
        printf 'Release: %s.\n' "$TAG"
    else
        printf 'Release: latest (resolved after confirmation).\n'
    fi
    printf 'Will run:\n'

    case "$METHOD" in
        aur)
            case "$AUR_MODE" in
                helper) printf '  %s -S --needed %s\n' "$AUR_HELPER" "$AUR_PACKAGE" ;;
                makepkg)
                    printf '  git clone https://aur.archlinux.org/%s.git <temp>\n' "$AUR_PACKAGE"
                    printf '  (cd <temp>/%s && makepkg -si --noconfirm)\n' "$AUR_PACKAGE"
                    ;;
                *)
                    printf '  print manual AUR instructions\n'
                    ;;
            esac
            ;;
        flatpak)
            printf '  download and verify the Flatpak bundle, source tarball, and SHA256SUMS\n'
            if (( USER_INSTALL )); then
                printf '  flatpak install --user --noninteractive <bundle>\n'
            else
                printf '  sudo flatpak install --system --noninteractive <bundle>\n'
            fi
            printf '  sudo ./install.sh --udev-only\n'
            ;;
        source)
            printf '  download and verify the source tarball and SHA256SUMS\n'
            if (( USER_INSTALL )); then
                printf '  ./install.sh --user\n'
                printf '  sudo ./install.sh --udev-only\n'
            else
                printf '  sudo ./install.sh\n'
            fi
            ;;
    esac
    printf 'Release assets downloaded by get.sh are checksum-verified before extraction or execution.\n'
}

normalize_base() {
    if [[ -n ${GET_SH_BASE_URL:-} ]]; then
        printf '%s/%s' "${GET_SH_BASE_URL%/}" "$TAG"
    else
        printf '%s/%s' "$RELEASE_BASE" "$TAG"
    fi
}

resolve_latest() {
    local api_file http_code response
    if [[ -n $TAG ]]; then
        return 0
    fi
    if [[ -n ${GET_SH_BASE_URL:-} ]]; then
        die "GET_SH_BASE_URL requires --version so the release tag is known"
    fi

    api_file="$TMP_DIR/release.json"
    if [[ $DOWNLOADER == curl ]]; then
        http_code=$(curl -sS -H 'Accept: application/vnd.github+json' -o "$api_file" -w '%{http_code}' "$API_URL" || true)
        if [[ $http_code != 200 ]]; then
            if [[ $http_code == 403 || $http_code == 429 ]] || grep -qi 'rate limit' "$api_file" 2>/dev/null; then
                die "GitHub API rate limit reached; try again later or pass --version vX.Y.Z"
            fi
            die "could not query the latest release (HTTP ${http_code:-unknown}); pass --version vX.Y.Z or try again"
        fi
    else
        if ! wget -q -O "$api_file" "$API_URL"; then
            if grep -qi 'rate limit' "$api_file" 2>/dev/null; then
                die "GitHub API rate limit reached; try again later or pass --version vX.Y.Z"
            fi
            die "could not query the latest release; pass --version vX.Y.Z or try again"
        fi
    fi

    response=$(grep -o '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' "$api_file" | head -n 1 | sed -E 's/.*"([^"]+)"$/\1/' || true)
    [[ -n $response ]] || die "could not read tag_name from the GitHub API response"
    TAG=$response
    if [[ $TAG != v* ]]; then
        die "latest release has an unexpected tag '$TAG'"
    fi
    VERSION=${TAG#v}
    if [[ ! $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z]+)*$ ]]; then
        die "latest release has an unexpected version '$VERSION'"
    fi
}

fetch_url() {
    local url=$1
    local dest=$2
    if [[ $DOWNLOADER == curl ]]; then
        curl -fsSL --retry 3 --connect-timeout 20 --output "$dest" "$url" || die "download failed: $url"
    else
        wget -q --tries=3 --timeout=20 -O "$dest" "$url" || die "download failed: $url"
    fi
}

download_sums() {
    fetch_url "$BASE/SHA256SUMS" "$TMP_DIR/SHA256SUMS"
    [[ -s $TMP_DIR/SHA256SUMS ]] || die "the release has an empty SHA256SUMS"
}

verify_asset() {
    local asset=$1
    local file=$2
    local expected actual count
    count=$(awk -v name="$asset" '$2 == name { count++ } END { print count+0 }' "$TMP_DIR/SHA256SUMS")
    expected=$(awk -v name="$asset" '$2 == name { print $1 }' "$TMP_DIR/SHA256SUMS")
    if [[ -z $expected || $count != 1 ]]; then
        die "SHA256SUMS has no unique entry for $asset"
    fi
    actual=$(sha256sum "$file" | awk '{print $1}')
    if [[ $actual != "$expected" ]]; then
        die "checksum mismatch for $asset; aborting before extraction or execution"
    fi
}

download_asset() {
    local asset=$1
    fetch_url "$BASE/$asset" "$TMP_DIR/$asset"
    verify_asset "$asset" "$TMP_DIR/$asset"
}

extract_source() {
    mkdir -p "$TMP_DIR/src"
    tar -xzf "$TMP_DIR/$ASSET_SOURCE" -C "$TMP_DIR/src"
    SRC_DIR="$TMP_DIR/src/madlions-control-${VERSION}"
    [[ -f $SRC_DIR/install.sh ]] || die "release tarball does not contain install.sh"
    [[ -f $SRC_DIR/uninstall.sh ]] || die "release tarball does not contain uninstall.sh"
}

check_installer_support() {
    if ! bash "$SRC_DIR/install.sh" --help 2>/dev/null | grep -q -- '--udev-only'; then
        die "Release ${TAG} is older than the installer requires; use --method aur or wait for the next release."
    fi
}

check_uninstaller_support() {
    if ! bash "$SRC_DIR/uninstall.sh" --help 2>/dev/null | grep -q -- '--udev-only'; then
        die "Release ${TAG} is older than this uninstaller requires; remove it manually or use the package manager."
    fi
}

write_state() {
    local method=$1
    local version=$2
    local user=$3
    local scope=${4:-}
    mkdir -p "$STATE_DIR"
    {
        printf 'method=%s\n' "$method"
        printf 'version=%s\n' "$version"
        printf 'user=%s\n' "$user"
        printf 'scope=%s\n' "$scope"
    } > "$STATE_FILE"
}

read_state() {
    local key value
    [[ -r $STATE_FILE ]] || return 1
    STATE_METHOD=""
    STATE_VERSION=""
    STATE_USER="0"
    STATE_SCOPE=""
    while IFS='=' read -r key value; do
        case "$key" in
            method) STATE_METHOD=$value ;;
            version) STATE_VERSION=$value ;;
            user) STATE_USER=$value ;;
            scope) STATE_SCOPE=$value ;;
        esac
    done < "$STATE_FILE"
    [[ -n $STATE_METHOD ]] || return 1
    case "$STATE_METHOD" in
        aur|flatpak|source) ;;
        *) die "state file has an unknown method '$STATE_METHOD'" ;;
    esac
    if [[ $STATE_METHOD != aur && -z $STATE_VERSION ]]; then
        die "state file is missing the installed version"
    fi
    return 0
}

replug_note() {
    say "Unplug and replug the keyboard so the udev rule takes effect."
}

install_aur() {
    local installed_version
    if [[ $AUR_MODE == manual ]]; then
        print_manual_aur
        exit 1
    fi

    if [[ $AUR_MODE == helper ]]; then
        run "$AUR_HELPER" -S --needed "$AUR_PACKAGE"
    else
        run git clone "https://aur.archlinux.org/${AUR_PACKAGE}.git" "$TMP_DIR/aur"
        run bash -c 'cd "$1" && makepkg -si --noconfirm' bash "$TMP_DIR/aur"
    fi

    installed_version=$(pacman -Q "$AUR_PACKAGE" 2>/dev/null | awk '{print $2}' || true)
    write_state aur "${installed_version:-unknown}" 0
    replug_note
}

install_flatpak() {
    local scope=system

    require_flatpak
    require_sudo
    if (( USER_INSTALL )); then
        scope=user
    fi

    download_sums
    download_asset "$ASSET_FLATPAK"
    download_asset "$ASSET_SOURCE"
    extract_source
    check_installer_support

    if [[ $scope == user ]]; then
        run flatpak install --user --noninteractive "$TMP_DIR/$ASSET_FLATPAK"
    else
        run sudo flatpak install --system --noninteractive "$TMP_DIR/$ASSET_FLATPAK"
    fi
    run sudo bash "$SRC_DIR/install.sh" --udev-only
    write_state flatpak "$VERSION" "$USER_INSTALL" "$scope"
    replug_note
}

install_source() {
    require_sudo
    download_sums
    download_asset "$ASSET_SOURCE"
    extract_source
    check_installer_support
    if (( USER_INSTALL )); then
        run bash "$SRC_DIR/install.sh" --user
        run sudo bash "$SRC_DIR/install.sh" --udev-only
    else
        run sudo bash "$SRC_DIR/install.sh"
    fi
    write_state source "$VERSION" "$USER_INSTALL"
    replug_note
}

run() {
    if (( DRY_RUN )); then
        printf '+'
        printf ' %q' "$@"
        printf '\n'
        return 0
    fi
    "$@"
}

dry_download() {
    local out=$1 url=$2
    if [[ $DOWNLOADER == curl ]]; then
        printf '+ curl -fsSL --retry 3 -o %s %s\n' "$out" "$url"
    else
        printf '+ wget -q -O %s %s\n' "$out" "$url"
    fi
}

# shellcheck disable=SC2016
print_dry_run_install() {
    local version_label="${VERSION:-<latest>}"
    local base
    if [[ -n $TAG ]]; then
        base=$(normalize_base)
    else
        base="https://github.com/${REPO}/releases/download/<latest>"
    fi

    printf '\nDry run commands:\n'
    printf '+ tmp=$(mktemp -d)\n'
    case "$METHOD" in
        aur)
            if [[ $AUR_MODE == helper ]]; then
                printf '+ %s -S --needed %s\n' "$AUR_HELPER" "$AUR_PACKAGE"
            elif [[ $AUR_MODE == makepkg ]]; then
                printf '+ git clone https://aur.archlinux.org/%s.git "$tmp/%s"\n' "$AUR_PACKAGE" "$AUR_PACKAGE"
                printf '+ (cd "$tmp/%s" && makepkg -si --noconfirm)\n' "$AUR_PACKAGE"
            else
                printf '+ print manual AUR instructions\n'
            fi
            ;;
        flatpak|source)
            dry_download "\$tmp/SHA256SUMS" "$base/SHA256SUMS"
            if [[ $METHOD == flatpak ]]; then
                dry_download "\$tmp/madlions-control-${version_label}-x86_64.flatpak" "$base/madlions-control-${version_label}-x86_64.flatpak"
            fi
            dry_download "\$tmp/madlions-control-${version_label}.tar.gz" "$base/madlions-control-${version_label}.tar.gz"
            printf '+ verify SHA256SUMS before extraction\n'
            printf '+ tar -xzf "$tmp/madlions-control-%s.tar.gz" -C "$tmp"\n' "$version_label"
            printf '+ bash "$tmp/madlions-control-%s/install.sh" --help # require --udev-only\n' "$version_label"
            if [[ $METHOD == flatpak ]]; then
                if (( USER_INSTALL )); then
                    printf '+ flatpak install --user --noninteractive "$tmp/madlions-control-%s-x86_64.flatpak"\n' "$version_label"
                else
                    printf '+ sudo flatpak install --system --noninteractive "$tmp/madlions-control-%s-x86_64.flatpak"\n' "$version_label"
                fi
                printf '+ sudo bash "$tmp/madlions-control-%s/install.sh" --udev-only\n' "$version_label"
            elif (( USER_INSTALL )); then
                printf '+ bash "$tmp/madlions-control-%s/install.sh" --user\n' "$version_label"
                printf '+ sudo bash "$tmp/madlions-control-%s/install.sh" --udev-only\n' "$version_label"
            else
                printf '+ sudo bash "$tmp/madlions-control-%s/install.sh"\n' "$version_label"
            fi
            ;;
    esac
}

print_no_state_uninstall() {
    cat <<EOF
No get.sh state file found at:
  $STATE_FILE

Remove the method you used:

  AUR:
    sudo pacman -Rns $AUR_PACKAGE

  Flatpak (user):
    flatpak uninstall --user -y $FLATPAK_ID

  Flatpak (system):
    sudo flatpak uninstall --system -y $FLATPAK_ID

  Source, system-wide:
    download the same release tarball, verify SHA256SUMS, then run:
    sudo ./uninstall.sh

  Source, user install:
    download the same release tarball, verify SHA256SUMS, then run:
    ./uninstall.sh --user
    sudo ./uninstall.sh --udev-only

After removing the host udev rule, unplug and replug the keyboard.
EOF
}

plan_uninstall() {
    local label=$STATE_METHOD
    case "$STATE_METHOD" in
        aur) label="AUR" ;;
        flatpak) label="Flatpak (${STATE_SCOPE:-user})" ;;
        source)
            if [[ $STATE_USER == 1 ]]; then
                label="source (user)"
            else
                label="source (system)"
            fi
            ;;
    esac
    printf 'Detected: %s, %s.\n' "$OS_NAME" "$ARCH"
    printf 'Will uninstall: %s, version %s.\n' "$label" "$STATE_VERSION"
    printf 'Will run:\n'
    case "$STATE_METHOD" in
        aur) printf '  sudo pacman -Rns %s\n' "$AUR_PACKAGE" ;;
        flatpak)
            if [[ $STATE_SCOPE == system ]]; then
                printf '  sudo flatpak uninstall --system -y %s\n' "$FLATPAK_ID"
            else
                printf '  flatpak uninstall --user -y %s\n' "$FLATPAK_ID"
            fi
            printf '  download and verify the source tarball\n'
            printf '  sudo ./uninstall.sh --udev-only\n'
            ;;
        source)
            printf '  download and verify the source tarball\n'
            if [[ $STATE_USER == 1 ]]; then
                printf '  ./uninstall.sh --user\n'
                printf '  sudo ./uninstall.sh --udev-only\n'
            else
                printf '  sudo ./uninstall.sh\n'
            fi
            ;;
    esac
    printf 'Profiles and settings are left in place.\n'
}

# shellcheck disable=SC2016
print_dry_run_uninstall() {
    local version_label=$STATE_VERSION
    printf '\nDry run commands:\n'
    case "$STATE_METHOD" in
        aur)
            printf '+ sudo pacman -Rns %s\n' "$AUR_PACKAGE"
            ;;
        flatpak)
            if [[ $STATE_SCOPE == system ]]; then
                printf '+ sudo flatpak uninstall --system -y %s\n' "$FLATPAK_ID"
            else
                printf '+ flatpak uninstall --user -y %s\n' "$FLATPAK_ID"
            fi
            dry_download "\$tmp/SHA256SUMS" "$BASE/SHA256SUMS"
            dry_download "\$tmp/madlions-control-${version_label}.tar.gz" "$BASE/madlions-control-${version_label}.tar.gz"
            printf '+ verify SHA256SUMS before extraction\n'
            printf '+ sudo bash "$tmp/madlions-control-%s/uninstall.sh" --udev-only\n' "$version_label"
            ;;
        source)
            dry_download "\$tmp/SHA256SUMS" "$BASE/SHA256SUMS"
            dry_download "\$tmp/madlions-control-${version_label}.tar.gz" "$BASE/madlions-control-${version_label}.tar.gz"
            printf '+ verify SHA256SUMS before extraction\n'
            if [[ $STATE_USER == 1 ]]; then
                printf '+ bash "$tmp/madlions-control-%s/uninstall.sh" --user\n' "$version_label"
                printf '+ sudo bash "$tmp/madlions-control-%s/uninstall.sh" --udev-only\n' "$version_label"
            else
                printf '+ sudo bash "$tmp/madlions-control-%s/uninstall.sh"\n' "$version_label"
            fi
            ;;
    esac
    printf '+ rm -f %s\n' "$STATE_FILE"
}

do_uninstall() {
    detect_os
    if ! read_state; then
        print_no_state_uninstall
        return 0
    fi
    if [[ $STATE_METHOD != aur ]]; then
        require_tools
        VERSION=$STATE_VERSION
        TAG="v${VERSION}"
        BASE=$(normalize_base)
        ASSET_SOURCE="madlions-control-${VERSION}.tar.gz"
    fi

    plan_uninstall
    if (( DRY_RUN )); then
        print_dry_run_uninstall
        return 0
    fi
    confirm "Remove Madlions Control now?"

    if [[ $STATE_METHOD == aur ]]; then
        require_sudo
        run sudo pacman -Rns "$AUR_PACKAGE"
        rm -f "$STATE_FILE"
        rmdir "$STATE_DIR" 2>/dev/null || true
        say "Removed the AUR package. Profiles and settings were left in place."
        return 0
    fi

    TMP_DIR=$(mktemp -d)
    trap cleanup EXIT
    download_sums
    download_asset "$ASSET_SOURCE"
    extract_source
    check_uninstaller_support

    case "$STATE_METHOD" in
        flatpak)
            require_flatpak
            if [[ $STATE_SCOPE == system ]]; then
                require_sudo
                run sudo flatpak uninstall --system -y "$FLATPAK_ID"
            else
                run flatpak uninstall --user -y "$FLATPAK_ID"
            fi
            require_sudo
            run sudo bash "$SRC_DIR/uninstall.sh" --udev-only
            ;;
        source)
            if [[ $STATE_USER == 1 ]]; then
                run bash "$SRC_DIR/uninstall.sh" --user
                require_sudo
                run sudo bash "$SRC_DIR/uninstall.sh" --udev-only
            else
                require_sudo
                run sudo bash "$SRC_DIR/uninstall.sh"
            fi
            ;;
    esac

    rm -f "$STATE_FILE"
    rmdir "$STATE_DIR" 2>/dev/null || true
    say "Removed Madlions Control. Profiles and settings were left in place."
}

main() {
    parse_args "$@"
    if (( SHOW_HELP )); then
        usage
        return 0
    fi
    if (( EUID == 0 )); then
        die "Run as your normal user; get.sh uses sudo only for the steps that need it."
    fi

    detect_os
    detect_downloader

    if (( UNINSTALL )); then
        do_uninstall
        return 0
    fi

    require_tools
    normalize_version
    choose_method
    check_existing_install
    plan_install

    if (( DRY_RUN )); then
        print_dry_run_install
        return 0
    fi
    confirm "Continue with this install?"

    TMP_DIR=$(mktemp -d)
    trap cleanup EXIT
    resolve_latest
    BASE=$(normalize_base)
    ASSET_SOURCE="madlions-control-${VERSION}.tar.gz"
    ASSET_FLATPAK="madlions-control-${VERSION}-x86_64.flatpak"

    case "$METHOD" in
        aur) install_aur ;;
        flatpak) install_flatpak ;;
        source) install_source ;;
    esac
}

main "$@"
