#!/bin/bash
# Interleaved fps A/B: the 1D site (ee8aace, :4174) vs Part A (:4173), same harness, fresh Firefox each.
cd "/home/gautham/ros2_ws(personal)/src/coco-robot-ros2/.claude/worktrees/lab1" || exit 1
J=/home/gautham/.claude/jobs/eb997671/tmp
for i in 1 2 3; do
  for side in old new; do
    port=4173; [ "$side" = old ] && port=4174
    out="$J/ab_${side}_$i"
    rm -rf "$out"
    timeout 600 python3 lab_web/tools/browser/check.py "http://127.0.0.1:$port/coco-robot-jazzy-2.0/" "$out" fps > /dev/null 2>&1
    python3 -c "
import json;d=json.load(open('$out/report.json'))['fps'];r=d['runs']
print('$side $i', {k:(v['fps'],v['dropped_frames_gap_over_25ms'],v['frames'],v['frame_gap_ms_max'],v['draw_ms_median'],v['draw_ms_p95']) for k,v in r.items()}, d.get('_loadavg'))"
  done
done
