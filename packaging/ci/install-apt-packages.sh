#!/usr/bin/env bash
# Install CI packages, falling back to kernel.org when Ubuntu's mirrors are
# unreachable from the runner (a recurring GitHub Actions DNS failure).
set -euo pipefail

use_fallback_mirror() {
    echo "Ubuntu mirror unreachable; switching to kernel.org" >&2
    sudo find /etc/apt -maxdepth 2 -type f \
        \( -name 'apt-mirrors.txt' -o -name 'sources.list' -o -name '*.sources' \) \
        -exec sed -i -E \
            -e 's|https?://(azure\.)?archive\.ubuntu\.com/ubuntu|https://mirrors.edge.kernel.org/ubuntu|g' \
            -e 's|https?://security\.ubuntu\.com/ubuntu|https://mirrors.edge.kernel.org/ubuntu|g' {} +
    sudo apt-get update
}

if ! getent hosts archive.ubuntu.com >/dev/null 2>&1 || \
   ! getent hosts security.ubuntu.com >/dev/null 2>&1; then
    use_fallback_mirror
elif ! sudo apt-get update; then
    use_fallback_mirror
fi

if ! sudo apt-get install -y "$@"; then
    use_fallback_mirror
    sudo apt-get install -y "$@"
fi
