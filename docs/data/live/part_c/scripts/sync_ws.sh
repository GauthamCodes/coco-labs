#!/usr/bin/env bash
# sync_ws.sh FILELIST: copy the worktree's tracked + new files (FILELIST,
# from `git ls-files -co --exclude-standard`, run in the worktree) onto the
# plain copy ~/coco_live_ws/src/coco-labs, which is what the overlay there
# is built from and what run_all_package_tests.sh tests. No --delete.
HERE="$(cd "$(dirname "$0")/../../../../.." && pwd)"
rsync -a --files-from="$1" "$HERE/" "$HOME/coco_live_ws/src/coco-labs/" \
  && echo "synced $(wc -l < "$1") paths from $HERE"
