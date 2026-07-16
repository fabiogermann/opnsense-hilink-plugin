#!/bin/sh
# Build a genuine FreeBSD package (installable with pkg add on OPNsense).
#
# The plugin contains no compiled code, so the package can be created on any
# platform that has the pkg(8) tool available - FreeBSD natively, or the
# static Linux build in CI (https://github.com/freebsd/pkg/releases).
#
# Usage: tools/build_pkg.sh <version> [output-dir]

set -eu

VERSION="${1:?usage: build_pkg.sh <version> [output-dir]}"
OUTDIR="${2:-dist}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$ROOT/build/stage"
META="$ROOT/build/meta"

command -v pkg >/dev/null 2>&1 || {
    echo "error: the pkg(8) tool is required (FreeBSD: base system," >&2
    echo "Linux: static build from https://github.com/freebsd/pkg/releases)" >&2
    exit 1
}

rm -rf "$STAGE" "$META"
mkdir -p "$STAGE/usr/local/opnsense" "$META" "$ROOT/$OUTDIR"

# Stage the plugin files at their final install locations
cp -R "$ROOT/src/opnsense/." "$STAGE/usr/local/opnsense/"
find "$STAGE" -name "*.pyc" -delete
find "$STAGE" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
chmod 755 "$STAGE/usr/local/opnsense/scripts/hilink/hilink_service.py" \
          "$STAGE/usr/local/opnsense/scripts/hilink/hilink_control.py"

# Inject the release version into the manifest (top-level version key only)
sed "s|^version: .*|version: \"$VERSION\"|" "$ROOT/pkg/+MANIFEST" > "$META/+MANIFEST"

# File list from the staged tree
(cd "$STAGE" && find . -type f | sed 's|^\.||' | sort) > "$META/pkg-plist"

pkg create -M "$META/+MANIFEST" -p "$META/pkg-plist" -r "$STAGE" \
    -o "$ROOT/$OUTDIR"

echo "created:"
ls -l "$ROOT/$OUTDIR"/os-hilink-"$VERSION".pkg
