#!/usr/bin/env bash
# Bump the version in the places that ship it.
set -euo pipefail
version="${1:?usage: bump-version.sh X.Y.Z}"
cd "$(dirname "$0")/.."
sed -i "s/^VERSION = .*/VERSION = \"$version\"/" madlions_control/config.py
sed -i "s/^version = .*/version = \"$version\"/" pyproject.toml
sed -i "s/^pkgver=.*/pkgver=$version/" PKGBUILD
sed -i "s/^pkgver=.*/pkgver=$version/" packaging/aur/madlions-control-git/PKGBUILD.in
grep -n "^VERSION\|^version" madlions_control/config.py pyproject.toml | head
