#!/usr/bin/env bash
# Build a Flatpak bundle.
#   ./packaging/flatpak/build.sh VERSION [OUTDIR]
# Requires flatpak and flatpak-builder with the GNOME 50 runtime/SDK installed.
set -euo pipefail

version="${1:?usage: build.sh <version> [output-dir]}"
out="${2:-dist}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
mkdir -p "$out"

rm -rf flatpak-build flatpak-repo
flatpak-builder --force-clean --disable-rofiles-fuse \
    --repo=flatpak-repo flatpak-build \
    packaging/flatpak/io.github.madlionscontrol.MadlionsControl.yml

flatpak build-bundle flatpak-repo \
    "$out/madlions-control-${version}-x86_64.flatpak" \
    io.github.madlionscontrol.MadlionsControl
echo "built $out/madlions-control-${version}-x86_64.flatpak"
