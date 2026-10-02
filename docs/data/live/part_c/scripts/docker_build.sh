#!/usr/bin/env bash
# docker_build.sh SRC_TREE: rsync a `git archive HEAD` export of the live
# branch onto the plain build copy (~/coco_live_ws/src/coco-labs; the
# worktree path has parentheses, see CLAUDE.md), then `docker compose build`.
# No --delete: the copy also holds lab_web/node_modules and build output.
SRC="$1"
REPO="$HOME/coco_live_ws/src/coco-labs"
[ -d "$SRC" ] || { echo "no source tree $SRC"; exit 1; }
rsync -a "$SRC/" "$REPO/" || exit 1
cd "$REPO" || exit 1
docker images coco-platform --format 'before: {{.Tag}} {{.ID}} {{.CreatedAt}}'
start=$(date +%s)
docker compose build 2>&1 | tail -20
rc=${PIPESTATUS[0]}
echo "build rc=$rc in $(( $(date +%s) - start )) s"
docker images coco-platform --format 'after: {{.Tag}} {{.ID}} {{.CreatedAt}}'
docker image inspect osrf/ros:jazzy-desktop --format 'base: {{.Id}} {{json .RepoDigests}}'
