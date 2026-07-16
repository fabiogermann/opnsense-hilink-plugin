#!/bin/sh
# Build a genuine FreeBSD package (installable with pkg add on OPNsense).
#
# The plugin contains no compiled code, so the package can be created on any
# platform that has the pkg(8) tool available - FreeBSD natively, or the
# static Linux build in CI (https://github.com/freebsd/pkg/releases).
#
# When building on a non-FreeBSD host (e.g. an Ubuntu CI runner), pkg create
# stamps the host ABI (linux:3.2:x86_64) into the manifest, producing a
# package that won't install on OPNsense ("wrong architecture").  After
# creating the package we rewrite abi+arch to the target FreeBSD ABI so it
# installs on the intended OS.  Override the target with TARGET_ABI, e.g.:
#     TARGET_ABI=freebsd:14:amd64 make package
# The default freebsd:*:* wildcard matches any FreeBSD version/arch, which is
# correct for a pure-Python/PHP plugin with no compiled objects.
#
# The ABI rewrite is done in Python (via the zstandard module) so it works
# the same on Linux and FreeBSD without depending on a tar+zstd CLI.  If
# zstandard is not importable (e.g. a native FreeBSD build that already has
# the correct ABI), the step is skipped.
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
# pkg create stamps the host ABI (e.g. linux:3.2:x86_64 on a Linux runner).
# Rewrite abi+arch to the target FreeBSD ABI so the package installs on
# OPNsense.  Non-fatal: on any error the package is left as-is and the build
# continues (native FreeBSD builds already have the correct ABI).
python3 - "$PKGFILE" "$TARGET_ABI" <<'PY'
import json, sys, tarfile, io
pkgpath, target_abi = sys.argv[1], sys.argv[2]
try:
    import zstandard as zstd
except ImportError:
    sys.exit(0)  # native build or zstandard unavailable
try:
    data = open(pkgpath, "rb").read()
    reader = zstd.ZstdDecompressor().stream_reader(io.BytesIO(data))
    raw = b"".join(iter(lambda: reader.read(65536), b""))
    tf = tarfile.open(fileobj=io.BytesIO(raw))
    mf = tf.extractfile("+MANIFEST")
    if mf is None:
        sys.exit(0)
    man = json.loads(mf.read().decode())
    if man.get("abi", "") == target_abi:
        sys.exit(0)
    man["abi"] = target_abi
    man["arch"] = target_abi
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as ntf:
        payload = json.dumps(man, separators=(",", ":")).encode()
        info = tarfile.TarInfo("+MANIFEST")
        info.size = len(payload)
        ntf.addfile(info, io.BytesIO(payload))
        for ti in tf.getmembers():
            if ti.name == "+MANIFEST":
                continue
            ntf.addfile(ti, tf.extractfile(ti))  # None for dirs/symlinks is fine
    open(pkgpath, "wb").write(zstd.ZstdCompressor(level=19).compress(out.getvalue()))
    print("rewrote package abi -> %s" % target_abi)
except Exception:
    pass  # leave package as-is
PY

echo "created:"
ls -l "$PKGFILE"
