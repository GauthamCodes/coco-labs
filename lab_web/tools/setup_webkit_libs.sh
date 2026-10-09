#!/usr/bin/env bash
# setup_webkit_libs.sh — re-create the private WebKit media libraries that let
# Playwright's WebKit (webkit-2370) run on this Ubuntu 24.04 host WITHOUT sudo.
#
#   lab_web/tools/setup_webkit_libs.sh [DEST]      default DEST: ~/coco_lab_m1_ws/webkit_libs
#
# What it does, and nothing more:
#   1. fetches four .debs at PINNED versions into DEST/debs (`apt-get download`,
#      which needs no root; if the archive has moved on, Launchpad's copy of the
#      same file), and refuses any whose sha256 is not the pinned one;
#   2. unpacks them with `dpkg -x` into DEST/root (no install, no maintainer
#      scripts, nothing outside DEST);
#   3. writes DEST/webkit_run.sh, a launcher that points WebKit at them.
# Nothing system-wide is installed or changed. Re-running is safe: a .deb that
# is already present with the right checksum is not fetched again.
#
# Use the launcher from Playwright (as lab_web/tools/perf/determinism.mjs does):
#   LD_LIBRARY_PATH=DEST/root/usr/lib/x86_64-linux-gnu \
#     node tools/perf/determinism.mjs webkit --webkit-exe DEST/webkit_run.sh ...
# (LD_LIBRARY_PATH is for Playwright's own host-dependency check; the launcher
# sets it for the browser itself.)
#
# Why these four: Playwright's WebKit build links libavif16, libgav1-1, libyuv0
# and libgstreamer-plugins-bad1.0-0, which this host does not have; installing
# them needs sudo, which COCO Lab sessions do not use (docs/v2/CHECKOUTS.md).
# Pinned 2026-10-09 from the copies M1 unpacked on 2026-10-09.
set -euo pipefail

DEST="${1:-$HOME/coco_lab_m1_ws/webkit_libs}"
WEBKIT="$HOME/.cache/ms-playwright/webkit-2370"

# package  version  sha256 of the .deb (amd64, Ubuntu 24.04 "noble")
PINS="
libavif16 1.0.4-1ubuntu3 b295a9954a4b756af05ff381d9808f3c0c582a111b7e4c7678cfe13de9ae8818
libgav1-1 0.18.0-1build3 428f353f449e6b15cdcf5823215416e36adcfba75fe9f0fedc1cd132d68e6b3f
libgstreamer-plugins-bad1.0-0 1.24.2-1ubuntu4 6e8da41c0cbb2070f3477cf02360c2ce2eb55e825ba09e12b4270b3254e04f45
libyuv0 0.0~git202401110.af6ac82-1 88bd472e50a7e45469e31f8e0ba232b4d8ed30322f5badb285c58cc1ba0d2176
"

[ -d "$WEBKIT" ] || { echo "Playwright WebKit not found at $WEBKIT (cd lab_web && npx playwright install webkit)" >&2; exit 1; }
mkdir -p "$DEST/debs" "$DEST/root"

sha_ok() { [ -f "$1" ] && [ "$(sha256sum "$1" | cut -d' ' -f1)" = "$2" ]; }

echo "$PINS" | while read -r pkg ver sha; do
  [ -n "$pkg" ] || continue
  # apt names the file with the epoch-free version, ':' escaped; none here has an epoch
  deb="${pkg}_${ver}_amd64.deb"
  path="$DEST/debs/$deb"
  if sha_ok "$path" "$sha"; then echo "ok (cached)  $deb"; continue; fi
  rm -f "$path"
  ( cd "$DEST/debs" && apt-get download "${pkg}=${ver}" >/dev/null 2>&1 ) || true
  if ! sha_ok "$path" "$sha"; then
    rm -f "$path"
    pool="https://launchpad.net/ubuntu/+archive/primary/+files/${deb//\~/%7E}"
    curl -fsSL -o "$path" "$pool" || true
  fi
  sha_ok "$path" "$sha" || { echo "FAILED  $deb: not found at the pinned sha256 $sha" >&2; rm -f "$path"; exit 1; }
  echo "ok (fetched) $deb"
done

for deb in "$DEST"/debs/*.deb; do dpkg -x "$deb" "$DEST/root"; done
LIB="$DEST/root/usr/lib/x86_64-linux-gnu"
for so in libavif.so.16 libgav1.so.1 libyuv.so.0 libgstcodecparsers-1.0.so.0; do
  [ -e "$LIB/$so" ] || { echo "FAILED  $so missing after unpacking" >&2; exit 1; }
done

cat > "$DEST/webkit_run.sh" <<EOF
#!/bin/sh
# Playwright WebKit (webkit-2370) with the private libraries in $DEST/root.
# Written by lab_web/tools/setup_webkit_libs.sh. Nothing system-wide is touched.
W="$WEBKIT"
case "\$*" in *--headless*) M="\$W/minibrowser-wpe" ;; *) M="\$W/minibrowser-gtk" ;; esac
export WEBKIT_EXEC_PATH="\$M/bin"
export WEBKIT_INJECTED_BUNDLE_PATH="\$M/lib"
export WEBKIT_INSPECTOR_RESOURCES_PATH="\$M/share"
export LD_LIBRARY_PATH="\$M/lib:\$M/sys/lib:$LIB"
export WEBKIT_FORCE_COMPLEX_TEXT=1
exec "\$M/bin/MiniBrowser" "\$@"
EOF
chmod +x "$DEST/webkit_run.sh"
echo "WebKit libraries ready in $DEST/root; launcher $DEST/webkit_run.sh"
