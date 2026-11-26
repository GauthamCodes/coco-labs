#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
#
# R5.1: measure before pulling. Decides whether this machine has room for an image WITHOUT
# pulling it, from two measurements:
#   - what a pull downloads: the registry manifest's compressed layer sizes (no layer is fetched);
#   - what it unpacks to: CI's measurement (size.json in the coco-ros2-image artifact of the run
#     that pushed the image: .github/workflows/coco-ros2-image.yml).
# Docker keeps both on disk after a pull with the containerd image store (the laptop's `docker
# images` shows DISK USAGE and CONTENT SIZE), so the need is unpacked + compressed, and KEEP_FREE
# bytes must stay free afterwards (a choice: 2,000,000,000 by default).
#
#   bash tools/r5/preflight_pull.sh IMAGE_REF SIZE_JSON [KEEP_FREE_BYTES]
#   e.g. bash tools/r5/preflight_pull.sh ghcr.io/gauthamcodes/coco-ros2:sha-0123456789ab out/size.json
#
# Prints one JSON record. Exit 0: room to pull; 1: no room (do not pull); 2: could not measure.
set -o pipefail
REF="${1:?usage: preflight_pull.sh IMAGE_REF SIZE_JSON [KEEP_FREE_BYTES]}"
SIZE_JSON="${2:?usage: preflight_pull.sh IMAGE_REF SIZE_JSON [KEEP_FREE_BYTES]}"
KEEP_FREE="${3:-2000000000}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if ! docker buildx imagetools inspect --raw "$REF" > "$TMP/top.json" 2> "$TMP/err.txt"; then
  echo "{\"ref\": \"$REF\", \"error\": \"no manifest: $(tr -d '"\n' < "$TMP/err.txt" | head -c 300)\"}"
  exit 2
fi
ROOT="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo /var/lib/docker)"
FREE="$(df -B1 --output=avail "$ROOT" 2>/dev/null | tail -n 1 | tr -d ' ')"

python3 - "$REF" "$TMP" "$SIZE_JSON" "$KEEP_FREE" "$FREE" "$ROOT" <<'PY'
import json, subprocess, sys
ref, tmp, size_json, keep, free, root = sys.argv[1:7]
top = json.load(open(f'{tmp}/top.json'))
man = top
if 'manifests' in top:
    d = next(m for m in top['manifests'] if m.get('platform', {}).get('architecture') == 'amd64'
             and m.get('platform', {}).get('os') == 'linux')
    base = ref.split('@')[0]
    if ':' in base.rsplit('/', 1)[-1]:      # drop a tag, never a registry's port
        base = base.rsplit(':', 1)[0]
    man = json.loads(subprocess.run(['docker', 'buildx', 'imagetools', 'inspect', '--raw',
                                     f'{base}@{d["digest"]}'], check=True, capture_output=True,
                                    text=True).stdout)
compressed = sum(l['size'] for l in man['layers']) + man['config']['size']
size = json.load(open(size_json))
unpacked = int(size['unpacked_bytes'])
need = unpacked + compressed + int(keep)
rec = {'ref': ref, 'measured_registry_compressed_bytes': compressed,
       'ci_registry_compressed_bytes': size.get('registry_compressed_bytes'),
       'ci_unpacked_bytes': unpacked, 'ci_git_sha': size.get('git_sha'),
       'docker_root': root, 'free_bytes': int(free), 'keep_free_bytes': int(keep),
       'need_bytes': need, 'room': int(free) >= need}
if size.get('registry_compressed_bytes') not in (None, compressed):
    rec['warning'] = 'the registry now serves a different image than CI measured for this size.json'
print(json.dumps(rec, indent=1, sort_keys=True))
sys.exit(0 if rec['room'] else 1)
PY
