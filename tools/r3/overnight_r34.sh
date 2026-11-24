#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
# R4 Part A: the missing Gazebo repeats (control and localisation, repeats 2 and 3), run overnight
# while the laptop is otherwise free. Gautham uses this laptop for his internship, so:
#  - before starting: no simulator, Isaac Sim, FR3 launch or ~/franka_ws process may be running;
#  - while running: if one appears, this SIGKILLs ITS OWN process group (never anyone else's) and logs
#    it (ros2_session.sh's own after-session ros_clean.sh matches launch names, so a foreign MoveIt
#    launch started DURING a session could be reached by it before this watchdog's 30 s poll: stated);
#    the queue is resumable (DONE sessions are skipped), so `tools/r3/overnight_r34.sh` continues later;
#  - the power profile is recorded, set to balanced (the queue's own requirement), and restored after.
#   tools/r3/overnight_r34.sh LOG
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG="${1:?usage: overnight_r34.sh LOG}"
FOREIGN='[i]saac|[f]ranka_ws|[f]r3_|[f]ranka_|[o]mni\.isaac'
say() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
if pgrep -f "$FOREIGN" > /dev/null || pgrep -f 'g[z] sim' > /dev/null; then
  say "NOT STARTED: another simulator / Isaac / FR3 / franka_ws process is running"; exit 3
fi
export COCO_WS="${COCO_WS:-$HOME/coco_lab_r3_ws}"
[ -f "$COCO_WS/install/local_setup.bash" ] || { say "NOT STARTED: no overlay at $COCO_WS"; exit 3; }
ORIG="$(powerprofilesctl get 2>/dev/null)"
say "start; power profile was '$ORIG'; AC $(cat /sys/class/power_supply/AC*/online 2>/dev/null)"
powerprofilesctl set balanced 2>/dev/null
# its own process group, so stopping it can never reach anyone else's processes
setsid "$R/tools/r3/ros2_queue_r34.sh" 2 3 >> "$LOG" 2>&1 &
Q=$!
while kill -0 "$Q" 2>/dev/null; do
  if pgrep -f "$FOREIGN" > /dev/null; then
    say "STOPPED: a foreign Isaac/FR3/franka_ws process appeared; killing our own process group $Q"
    # SIGKILL the group: no teardown runs, because ros_clean.sh matches launch files by name
    # (move_group, rsp, ...) and could reach an FR3/MoveIt launch that is not ours
    kill -KILL -- "-$Q" 2>/dev/null
    break
  fi
  sleep 30
done
wait "$Q" 2>/dev/null
say "queue exited rc=$?; restoring power profile '$ORIG'"
[ -n "$ORIG" ] && powerprofilesctl set "$ORIG" 2>/dev/null
say "done"
