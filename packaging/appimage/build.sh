#!/usr/bin/env bash
# Build a lean AppImage: application code only, host provides the GTK stack.
#   ./packaging/appimage/build.sh VERSION [OUTDIR]
set -euo pipefail

version="${1:?usage: build.sh <version> [output-dir]}"
out="${2:-dist}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
mkdir -p "$out"

rm -rf AppDir
mkdir -p AppDir/usr/share/madlions-control
cp -r madlions_control data AppDir/usr/share/madlions-control/
find AppDir/usr/share/madlions-control -name '__pycache__' -type d -prune -exec rm -rf {} +
install -Dm755 packaging/appimage/AppRun AppDir/AppRun
install -Dm644 packaging/appimage/launcher.py AppDir/usr/share/madlions-control/launcher.py
install -Dm644 data/icons/madlions-control-256.png AppDir/madlions-control.png
install -Dm644 data/icons/madlions-control-256.png \
    AppDir/io.github.madlionscontrol.MadlionsControl.png
install -Dm644 data/icons/hicolor/scalable/apps/io.github.madlionscontrol.MadlionsControl.svg \
    AppDir/madlions-control.svg
install -Dm644 data/icons/hicolor/scalable/apps/io.github.madlionscontrol.MadlionsControl.svg \
    AppDir/io.github.madlionscontrol.MadlionsControl.svg
install -Dm644 data/io.github.madlionscontrol.MadlionsControl.desktop AppDir/madlions-control.desktop
install -Dm644 data/io.github.madlionscontrol.MadlionsControl.desktop \
    AppDir/usr/share/applications/madlions-control.desktop
install -Dm644 data/metainfo/io.github.madlionscontrol.MadlionsControl.metainfo.xml \
    AppDir/usr/share/metainfo/io.github.madlionscontrol.MadlionsControl.metainfo.xml
ln -sf io.github.madlionscontrol.MadlionsControl.png AppDir/.DirIcon
chmod -R a+rX AppDir

tool="${APPIMAGETOOL:-/tmp/appimagetool-1.9.1-x86_64.AppImage}"
if [[ -z "${APPIMAGETOOL:-}" ]]; then
    tool_version="1.9.1"
    sha256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
    if [[ ! -x "$tool" ]] || ! printf '%s  %s\n' "$sha256" "$tool" | sha256sum -c - >/dev/null 2>&1; then
        curl -fsSL "https://github.com/AppImage/appimagetool/releases/download/${tool_version}/appimagetool-x86_64.AppImage" -o "$tool"
        chmod +x "$tool"
    fi
    printf '%s  %s\n' "$sha256" "$tool" | sha256sum -c -
fi

ARCH=x86_64 "$tool" --appimage-extract-and-run "AppDir" \
    "$out/madlions-control-${version}-x86_64.AppImage"
echo "built $out/madlions-control-${version}-x86_64.AppImage"
