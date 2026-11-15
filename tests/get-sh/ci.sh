#!/usr/bin/env bash
# Container-side checks for get.sh. Run as root inside a disposable container.
set -euo pipefail
umask 022

MODE=${1:-dry-run}
EXPECTED=${2:-}
ROOT=${GITHUB_WORKSPACE:-/work}
GET_SH="$ROOT/get.sh"
STATE_FILE="/home/tester/.local/state/madlions-control/get-sh.state"
VERSION="0.4.0"
PORT="8877"
SERVER_PID=""
WORK=""

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

cleanup() {
    if [[ -n $SERVER_PID ]]; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    if [[ -n $WORK ]]; then
        rm -rf "$WORK"
    fi
}
trap cleanup EXIT

[[ $EUID -eq 0 ]] || die "run this test as root inside the container"
[[ -f $GET_SH ]] || die "missing $GET_SH"
chmod 755 "$GET_SH"

install_packages() {
    if command -v apt-get >/dev/null 2>&1; then
        export DEBIAN_FRONTEND=noninteractive
        apt-get update
        local packages=(sudo curl ca-certificates tar gzip coreutils git python3 passwd util-linux)
        if [[ $MODE == integration ]]; then
            packages+=(
                python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
                gir1.2-pango-1.0 python3-cairo hicolor-icon-theme
            )
        fi
        apt-get install -y --no-install-recommends "${packages[@]}"
    elif command -v dnf >/dev/null 2>&1; then
        local packages=(sudo curl tar gzip coreutils git shadow-utils python3 util-linux)
        if [[ $MODE == dry-run ]]; then
            packages+=(flatpak)
        fi
        dnf install -y "${packages[@]}"
    elif command -v pacman >/dev/null 2>&1; then
        pacman -Sy --noconfirm --needed sudo curl tar gzip coreutils git shadow util-linux base-devel
    else
        die "unsupported container: no apt-get, dnf or pacman"
    fi
}

create_user() {
    if ! id tester >/dev/null 2>&1; then
        useradd -m -s /bin/bash tester
    fi
    printf 'tester ALL=(ALL) NOPASSWD:ALL\n' >/etc/sudoers.d/tester
    chmod 440 /etc/sudoers.d/tester
}

as_tester() {
    local command=$1
    su -s /bin/bash tester -c "cd $(printf '%q' "$ROOT") && HOME=/home/tester $command"
}

make_release() {
    local version=$1
    local directory=$2
    local tarball="madlions-control-${version}.tar.gz"

    mkdir -p "$directory"
    tar -czf "$directory/$tarball" \
        --transform "s,^,madlions-control-${version}/," \
        -C "$ROOT" install.sh uninstall.sh madlions_control data
    (
        cd "$directory"
        sha256sum "$tarball" >SHA256SUMS
    )
}

start_server() {
    local directory=$1
    python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$directory" \
        >/tmp/get-sh-http.log 2>&1 &
    SERVER_PID=$!
    sleep 1
    kill -0 "$SERVER_PID" 2>/dev/null || die "python http.server did not start"
}

run_install() {
    as_tester "GET_SH_BASE_URL=http://127.0.0.1:$PORT ./get.sh --version v$VERSION --method source --yes"
}

run_uninstall() {
    as_tester "GET_SH_BASE_URL=http://127.0.0.1:$PORT ./get.sh --uninstall --yes"
}

check_installed() {
    [[ -x /usr/bin/madlions-control ]] || die "system install did not create /usr/bin/madlions-control"
    [[ -f /usr/lib/udev/rules.d/71-madlions.rules ]] || die "system install did not create the prefix udev rule"
    [[ ! -e /etc/udev/rules.d/71-madlions.rules ]] || die "system install wrote an /etc udev rule"
    [[ -f $STATE_FILE ]] || die "get.sh did not write its state file"
}

check_uninstalled() {
    [[ ! -e /usr/bin/madlions-control ]] || die "uninstall left /usr/bin/madlions-control"
    [[ ! -e /usr/lib/madlions-control ]] || die "uninstall left /usr/lib/madlions-control"
    [[ ! -e /usr/lib/udev/rules.d/71-madlions.rules ]] || die "uninstall left the prefix udev rule"
    [[ ! -e /etc/udev/rules.d/71-madlions.rules ]] || die "uninstall left an /etc udev rule"
    [[ ! -e $STATE_FILE ]] || die "uninstall left the get.sh state file"
    [[ -f /etc/udev/rules.d/71-atk-control.rules ]] || die "uninstall removed the ATK rule"
}

integration() {
    [[ $MODE == integration ]] || die "integration called in $MODE mode"
    install_packages
    create_user

    WORK=$(mktemp -d)
    local release="$WORK/release"
    make_release "$VERSION" "$release/v$VERSION"
    start_server "$release"

    mkdir -p /etc/udev/rules.d
    printf '# sentinel\n' >/etc/udev/rules.d/71-atk-control.rules

    run_install
    check_installed

    run_uninstall
    check_uninstalled
    rm -f /etc/udev/rules.d/71-atk-control.rules

    local old="$WORK/old"
    mkdir -p "$old/v0.3.3/package"
    printf '#!/bin/sh\necho "legacy installer"\n' >"$old/v0.3.3/package/install.sh"
    printf '#!/bin/sh\necho "legacy uninstaller"\n' >"$old/v0.3.3/package/uninstall.sh"
    chmod 755 "$old/v0.3.3/package/"*.sh
    tar -czf "$old/v0.3.3/madlions-control-0.3.3.tar.gz" \
        --transform 's,^\./,madlions-control-0.3.3/,' \
        -C "$old/v0.3.3/package" .
    (
        cd "$old/v0.3.3"
        sha256sum madlions-control-0.3.3.tar.gz >SHA256SUMS
    )
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    SERVER_PID=""
    start_server "$old"

    local output rc
    set +e
    output=$(as_tester "GET_SH_BASE_URL=http://127.0.0.1:$PORT ./get.sh --version v0.3.3 --method source --yes" 2>&1)
    rc=$?
    set -e
    printf '%s\n' "$output"
    [[ $rc -ne 0 ]] || die "old release was accepted"
    grep -q 'older than the installer requires' <<<"$output" || die "old release abort message missing"

    local bad="$WORK/bad"
    make_release "$VERSION" "$bad/v$VERSION"
    (
        cd "$bad/v$VERSION"
        printf '%064d  madlions-control-%s.tar.gz\n' 0 "$VERSION" >SHA256SUMS
    )
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    SERVER_PID=""
    start_server "$bad"

    set +e
    output=$(run_install 2>&1)
    rc=$?
    set -e
    printf '%s\n' "$output"
    [[ $rc -ne 0 ]] || die "corrupt tarball was accepted"
    grep -q 'checksum mismatch' <<<"$output" || die "corrupt tarball did not report a checksum failure"
    [[ ! -e /usr/bin/madlions-control ]] || die "corrupt tarball reached the installer"

    printf 'PASS: get.sh integration (install, uninstall, old release, corrupt checksum)\n'
}

dry_run() {
    install_packages
    create_user
    local output
    output=$(as_tester './get.sh --dry-run --yes' 2>&1)
    printf '%s\n' "$output"
    grep -Fq "Method: $EXPECTED" <<<"$output" || die "expected method '$EXPECTED' was not selected"
    printf 'PASS: get.sh dry-run method = %s\n' "$EXPECTED"
}

main() {
    [[ $MODE == dry-run || $MODE == integration ]] || die "mode must be dry-run or integration"
    [[ $MODE == integration || -n $EXPECTED ]] || die "dry-run needs an expected method"

    if "$GET_SH" --dry-run --yes >/tmp/get-sh-root.log 2>&1; then
        die "get.sh did not refuse to run as root"
    fi
    grep -q 'Run as your normal user' /tmp/get-sh-root.log || die "root refusal message missing"

    if [[ $MODE == dry-run ]]; then
        dry_run
    else
        integration
    fi
}

main "$@"
