#!/bin/bash
# Public-site HTTP checks: status, type, encoding, size, gzip magic, and byte equality with the local build.
# Usage: http_check.sh [site-url] [local lab_web/dist to compare against]
# (Phase 1 closure, 2026-09-30; output recorded in http_check.txt.)
U="${1:-https://gauthamcodes.github.io/coco-labs/}"
L="${2:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)/lab_web/dist}"
T="$(mktemp -d)"
for p in "" index.html generated/catalog.json; do
  curl -s -o /dev/null -w "%{http_code} %{content_type} %{size_download}B  /$p\n" "$U$p"
done
curl -s "$U" -o "$T/index.html"
echo "asset refs in live index.html:"; grep -oE '(src|href)="[^"]+"' "$T/index.html"
for a in $(grep -oE '(src|href)="[^"]+"' "$T/index.html" | sed -E 's/.*="([^"]+)"/\1/' | grep -v '^http'); do
  curl -s -o /dev/null -w "  %{http_code} %{content_type} %{size_download}B $a\n" "https://gauthamcodes.github.io$a"
done
curl -s -o /dev/null -w "worker: %{http_code} %{size_download}B\n" "${U}assets/$(ls "$L/assets" | grep worker)"
echo "--- arrays.bin.gz on Pages (raw, no Accept-Encoding):"
for b in arena_native dijkstra_cost_field_gz arena_0_10m lab1c_astar lab1c_greedy lab1c_dijkstra; do
  f="generated/bundles/$b/arrays.bin.gz"
  hdr=$(curl -s -D - -o "$T/$b.gz" "$U$f" | tr -d '\r' | grep -iE "^(HTTP|content-type|content-encoding)" | tr '\n' ' ')
  magic=$(head -c2 "$T/$b.gz" | od -An -tx1 | tr -d ' ')
  if cmp -s "$T/$b.gz" "$L/$f"; then same=identical; else same=DIFFERENT; fi
  echo "  $b: $hdr| magic=$magic | vs local dist: $same"
done
echo "--- same, with Accept-Encoding: gzip (browser-like):"
curl -s -D - -o /dev/null -H 'Accept-Encoding: gzip, deflate, br' "${U}generated/bundles/lab1c_astar/arrays.bin.gz" | tr -d '\r' | grep -iE "^(HTTP|content-type|content-encoding)"
echo "--- 404 check:"; curl -s -o /dev/null -w "%{http_code}\n" "${U}generated/bundles/nope/arrays.bin.gz"
