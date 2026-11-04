#!/usr/bin/env bash
# Regenerate the screenshots used by the README and AppStream metadata.
# Requires: xvfb-run, ImageMagick (import/convert), python-xlib.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
out="docs/screenshots"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$out"

export XDG_CONFIG_HOME="$tmp/config"
export XDG_DATA_HOME="$tmp/data"
export MADLIONS_CONTROL_PROFILES="$tmp/profiles"
export MADLIONS_NO_TOOLTIPS=1
mkdir -p "$MADLIONS_CONTROL_PROFILES"
python3 - <<'PY'
from madlions_control import profiles, state as state_mod
from madlions_control.demo import DemoBackend

backend = DemoBackend()
state = state_mod.load_basic(backend)
state = state_mod.load_colors(backend, state)
profiles.Profile.capture(
    state,
    "My setup",
    "Everyday tuning with a little more travel on the modifiers.",
    full=False,
).save()
PY

shot() {
    page="$1"
    name="$2"
    shift 2
    echo "== $page"
    xvfb-run -a -s "-screen 0 1400x900x24" bash -c '
        export GDK_BACKEND=x11
        page="$1"
        base="$2"
        shift 2
        python3 -m madlions_control --demo --page "$page" >"$base.log" 2>&1 &
        pid=$!
        sleep 5
        for click in "$@"; do
            x="${click%,*}"
            y="${click#*,}"
            python3 tools/click.py "$x" "$y" || true
            sleep 0.8
        done
        read -r wx wy ww wh <<<"$(python3 tools/window_geometry.py)"
        import -window root "$base.raw.png" 2>/dev/null
        echo "$wx $wy $ww $wh" > "$base.geometry"
        kill $pid 2>/dev/null || true
        wait $pid 2>/dev/null || true
        if grep -q "Traceback" "$base.log"; then
            cat "$base.log"
            exit 1
        fi
    ' _ "$page" "$tmp/$name" "$@"
    wx=""; wy=""; ww=""; wh=""
    read -r wx wy ww wh < "$tmp/$name.geometry"
    convert "$tmp/$name.raw.png" -crop "${ww}x${wh}+${wx}+${wy}" +repage "$out/$name.png"
    echo "   $out/$name.png (${ww}x${wh})"
}

shot overview overview
shot perkey per-key
shot lighting lighting
shot keymap keymap 513,400
shot advanced advanced
shot test test
shot profiles profiles
ls -lh "$out"
