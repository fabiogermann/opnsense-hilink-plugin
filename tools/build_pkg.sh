#!/bin/sh
# Build a genuine FreeBSD package (installable with pkg add on OPNsense).
#
# The plugin contains no compiled code, so the package can be created on any
# platform that has the pkg(8) tool available - FreeBSD natively, or the
# static Linux build in CI (https://github.com/freebsd/pkg/releases).
#
# When building on a non-FreeBSD host (e.g. an Ubuntu CI runner), pkg create
# stamps the host ABI (linux:3.2:x86_64) into the manifest, producing a
# package that won't install on OPNsense.  After creating the package we
# rewrite abi+arch to the target FreeBSD ABI so it installs on the intended
# OS.  Override the target with TARGET_ABI, e.g.:
#     TARGET_ABI=freebsd:14:amd64 make package
# The default freebsd:*:* wildcard matches any FreeBSD version/arch, which is
# correct for a pure-Python/PHP plugin with no compiled objects.
#
# Usage: tools/build_pkg.sh <version> [output-dir]

set -eu

VERSION="${1:?usage: build_pkg.sh <version> [output-dir]}"
OUTDIR="${2:-dist}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$ROOT/build/stage"
META="$ROOT/build/meta"
TARGET_ABI="${TARGET_ABI:-freebsd:*:*}"

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
(cd "$STAGE" && find . -type f | sed 's|^\./||' | sort) > "$META/pkg-plist"

pkg create -M "$META/+MANIFEST" -p "$META/pkg-plist" -r "$STAGE" \
    -o "$ROOT/$OUTDIR"

PKGFILE="$ROOT/$OUTDIR/os-hilink-$VERSION.pkg"

# --- Fix the stamped ABI for cross-builds -------------------------------------
# pkg create writes the host's abi/arch into the manifest.  When that differs
# from the target (e.g. building on Linux for FreeBSD), rewrite it.  Requires
# tar with zstd support (FreeBSD bsdtar, or GNU tar + the zstd binary).
STAMPED="$(tar --zstd -xOf "$PKGFILE" +MANIFEST 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("abi",""))' \
    2>/dev/null || true)"
if [ -n "$STAMPED" ] && [ "$STAMPED" != "$TARGET_ABI" ]; then
    tmp="$(mktemp -d)"
    tar --zstd -xf "$PKGFILE" -C "$tmp"
    python3 - "$tmp/+MANIFEST" "$TARGET_ABI" <<'PY'
import json, sys
path, abi = sys.argv[1], sys.argv[2]
m = json.load(open(path))
m["abi"] = abi
m["arch"] = abi
with open(path, "w") as f:
    json.dump(m, f, separators=(",", ":"))
PY
    tar --zstd -cf "$PKGFILE" -C "$tmp" .
    rm -rf "$tmp"
    echo "rewrote package abi: $STAMPED -> $TARGET_ABI"
else
    echo "package abi already correct ($STAMPED)"
fi

echo "created:"
ls -l "$PKGFILE"
