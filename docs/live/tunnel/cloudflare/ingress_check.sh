#!/usr/bin/env bash
# ingress_check.sh [HOSTNAME] -- check the Cloudflare ingress rules OFFLINE.
#
# Renders config.yml.template with a dummy tunnel id (and HOSTNAME, default
# coco.example.invalid), then asks cloudflared itself which rule each URL
# matches: `tunnel ingress validate` and `tunnel ingress rule <url>`. The
# container runs with --network none: no tunnel is created or connected.
# Needs the docker group (run under `sg docker -c`).
set -o pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
HOST="${1:-coco.example.invalid}"
IMG="${COCO_CLOUDFLARED_IMAGE:-cloudflare/cloudflared:latest}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
sed -e "s/COCO_TUNNEL_UUID/00000000-0000-0000-0000-000000000000/g" \
    -e "s/COCO_TUNNEL_HOSTNAME/$HOST/g" \
    "$HERE/config.yml.template" > "$WORK/config.yml"
chmod 0644 "$WORK/config.yml"; chmod 0755 "$WORK"
cf() {
  docker run --rm --network none -v "$WORK:/etc/cloudflared:ro" "$IMG" \
    tunnel --config /etc/cloudflared/config.yml "$@" 2>&1
}
echo "== image"
docker image inspect -f '{{index .RepoDigests 0}}' "$IMG"
docker run --rm --network none "$IMG" --version
echo "== ingress validate"
cf ingress validate
echo "== which rule each URL matches (rule 0 = /ws, 1 = /healthz, 2 = catch-all 404)"
for url in \
  "https://$HOST/ws" "https://$HOST/healthz" "https://$HOST/ws?code=x" \
  "https://$HOST/" "https://$HOST/index.html" "https://$HOST/api/session" \
  "https://$HOST/api/metrics" "https://$HOST/video/camera" \
  "https://$HOST/ws/" "https://$HOST/wsx" "https://$HOST/ws/../api/session" \
  "https://$HOST/healthz/x" "https://$HOST/.git/config" \
  "https://other.example.invalid/ws" "https://other.example.invalid/healthz"; do
  printf '%-48s ' "$url"
  cf ingress rule "$url" | grep -E "Matched rule|service" | tr '\n' ' '
  echo
done
