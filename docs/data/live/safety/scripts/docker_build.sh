#!/usr/bin/env bash
# Sync the live worktree and build the compose image from the plain copy.
bash /home/gautham/.claude/jobs/eb997671/tmp/sync_build.sh --sync-only || exit 1
cd "$HOME/coco_live_ws/src/coco-labs" || exit 1
docker images coco-platform --format 'before: {{.Tag}} {{.ID}} {{.CreatedAt}}'
start=$(date +%s)
docker compose build
rc=$?
echo "build rc=$rc in $(( $(date +%s) - start )) s"
docker images coco-platform --format 'after: {{.Tag}} {{.ID}} {{.CreatedAt}}'
