# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Record Lab 3's demo video in headless Firefox (viewport only).

The same recorder as Labs 1 and 2 (``record_demo.py``: viewport frames at
their real timestamps, captions as a fixed strip added by this script, cuts
listed in ``cuts.json``). The one-time Pyodide start-up is run before
recording; every coco_lab run shown afterwards is recorded in full, in
real time, and its wait is CUT and listed in ``cuts.json``.

Usage::

    python3 lab_web/tools/browser/record_lab3_demo.py <site-url> <outdir>
"""

import asyncio
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check  # noqa: E402
from record_demo import encode, hold, Recorder, W, H  # noqa: E402

DONE = check.MAP_DONE


async def set_select_aria(s, aria, value):
    await s.js("(() => { const e = document.querySelector(" + json.dumps(f'select[aria-label="{aria}"]') + ");"
               " const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
               f" set.call(e, {json.dumps(value)}); e.dispatchEvent(new Event('change', {{ bubbles: true }}));"
               " return 1; })()")


async def top(s):
    await s.js('window.scrollTo(0, 0), 1')


async def wait_cut(s, what, expr, timeout=600):
    """Wait for coco_lab off camera (record_demo.Recorder.cut lists it)."""
    await s.cut(what, s.wait(expr, timeout=timeout, every=0.1))


async def tour(s):
    site = s.site
    await s.open('?view=map&scene=map_loop')
    await s.wait(check.MAP_READY, timeout=120)
    t_warm = time.monotonic()
    await check.click_testid(s, 'map-run')
    await s.wait(DONE, timeout=900, every=0.2)
    await s.open('?view=map&scene=map_loop')
    await s.wait(check.MAP_READY, timeout=120)
    await asyncio.sleep(1.0)
    await top(s)
    s.cuts.append({'what': 'before recording: the one-time Pyodide start-up and a warm-up run',
                   'seconds_cut': round(time.monotonic() - t_warm, 2), 'at_video_s': 0.0})

    s.recording = True
    await s.caption("COCO Lab 3 — Map. Sketch: coco_lab's 2D model of COCO, not the robot")
    await hold(4.0)
    await s.caption('Predict first: will closing the loop make the pose graph better here?')
    b = await s.js("(() => { const e = document.querySelector('.predict input[type=radio]');"
                   " e.scrollIntoView({block: 'center'}); const r = e.getBoundingClientRect();"
                   " return [r.left, r.top, r.width, r.height]; })()")
    await s.b.click(s.ctx, b[0] + b[2] / 2, b[1] + b[3] / 2)
    await hold(1.0)
    await top(s)
    await s.caption('Play: the LiDAR at the belief, the map it builds, the pose graph (thick: loop closures)')
    await set_select_aria(s, 'Playback speed', '16')
    await check.click_testid(s, 'map-play')
    await top(s)
    await hold(10.0)
    await check.click_testid(s, 'map-end')
    await s.caption('The final map against the truth: green right, orange not there, blue missed (coco_lab scores it)')
    await check.click_testid(s, 'map-show-diff')
    await top(s)
    await hold(5.0)
    await check.click_testid(s, 'map-show-diff')
    await check.click_testid(s, 'map-reveal')
    await s.caption('Reveal: with and without loop closure, on the same world')
    await s.js("(document.querySelector('[data-testid=map-revealed]').scrollIntoView({block: 'center'}), 1)")
    await hold(5.0)
    await top(s)
    await s.caption('Compare: one map per algorithm — same drive, same odometry, same scans')
    await check.click_testid(s, 'map-race-toggle')
    await top(s)
    await hold(4.0)
    await s.js("(document.querySelector('[data-testid=map-race]').scrollIntoView({block: 'center'}), 1)")
    await hold(5.0)
    await check.click_testid(s, 'map-race-toggle')
    await top(s)
    await s.caption('EKF-SLAM on an IDEALISED landmark sensor (box corners, identity known) — COCO has none')
    await set_select_aria(s, 'Whose map and belief', 'ekf_slam')
    await top(s)
    await hold(5.0)
    await s.caption('The featureless corridor: a scan cannot tell how far along it the robot is')
    await s.js("(() => { const e = document.querySelector('[data-testid=map-picker]');"
               " const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
               " set.call(e, 'map_corridor'); e.dispatchEvent(new Event('change', { bubbles: true })); return 1; })()")
    await s.wait(check.MAP_READY, timeout=60)
    await check.click_testid(s, 'map-race-toggle')
    await check.click_testid(s, 'map-end')
    await top(s)
    await hold(4.0)
    await s.js("(document.querySelector('[data-testid=map-race]').scrollIntoView({block: 'center'}), 1)")
    await hold(5.0)
    await check.click_testid(s, 'map-race-toggle')
    await top(s)
    await s.caption('Change it: a new world — coco_lab plans the drive and reruns every algorithm in your browser')
    await check.click_testid(s, 'map-new-world')
    await check.click_testid(s, 'map-run')
    await wait_cut(s, 'coco_lab rerunning the corridor world in the browser (Pyodide)', DONE)
    await top(s)
    await hold(6.0)
    await s.caption("The challenge: map COCO's arena. Fixed start, seed and noise — you choose the drive")
    await check.click_testid(s, 'map-sub-challenge')
    await s.wait(check.MAP_READY.replace(' && window.__cocoLabMap', ''), timeout=90)
    await top(s)
    await hold(4.0)
    await check.click_testid(s, 'map-clear')
    # the challenge starts with drawing ON: toggle only if it is off
    if not await s.js("document.querySelector('[data-testid=map-draw]')"
                      ".getAttribute('aria-pressed') === 'true'"):
        await check.click_testid(s, 'map-draw')
    cb = await check.box_of(s, 'slam-canvas')
    # the arena map is 25 x 19 m, origin (-6.5, -9.5): a loop round the north half and back
    # the default drive's waypoints (map_teaching.ARENA_ROUTE: each >= 0.5 m
    # from a wall), clicked; a click too near a wall is REFUSED with a reason
    for x, y in ((6.0, 0.0), (11.45, 2.15), (11.45, 7.75), (-1.45, 7.5), (-1.25, 0.5), (1.0, 0.0)):
        await s.b.click(s.ctx, cb[0] + cb[2] * (x + 6.5) / 25.0, cb[1] + cb[3] * (1 - (y + 9.5) / 19.0))
        await hold(0.7)
    await check.click_testid(s, 'map-draw')
    await s.caption('Drive it and map it: the score is round(100 x F1) of the map, computed by coco_lab')
    await check.click_testid(s, 'map-challenge-run')
    await wait_cut(s, 'coco_lab mapping the challenge drive in the browser (Pyodide)',
                   "(() => { const e = [...document.querySelectorAll('.edit-status')].pop();"
                   " return !!(e && !e.classList.contains('busy')); })()")
    await check.click_testid(s, 'map-end')
    await s.js("(document.querySelector('[data-testid=map-challenge-score]').scrollIntoView({block: 'center'}), 1)")
    await hold(6.0)
    await top(s)
    await s.caption("Replay: COCO's real 121 m tour, recorded in Gazebo, replayed into slam_toolbox and Cartographer")
    await check.click_testid(s, 'map-sub-replay')
    await s.wait(check.MAP_READY.replace(' && window.__cocoLabMap', ''), timeout=120)
    await top(s)
    await hold(5.0)
    for rid, cap in (('cartographer_loop', 'Cartographer with global SLAM on — its map, aligned to the truth'),
                     ('cartographer_noloop', 'The same Cartographer with global SLAM off'),
                     ('pose_graph', "coco_lab's pose graph on the same scans and odometry")):
        await s.caption(cap)
        await set_select_aria(s, 'Whose map and belief', rid)
        await top(s)
        await hold(4.5)
    await s.caption('Every run on both drives, scored by one definition, with the machine load beside it')
    await s.js("(document.querySelector('[data-testid=map-score-table]').scrollIntoView({block: 'start'}), 1)")
    await hold(6.0)
    await s.caption(f'Try it: {site}?view=map')
    await top(s)
    await hold(3.0)
    s.recording = False
    await asyncio.sleep(0.3)


async def main(argv):
    site, out = argv[0], argv[1]
    os.makedirs(out, exist_ok=True)
    frame_dir = os.path.join(out, 'frames')
    shutil.rmtree(frame_dir, ignore_errors=True)
    os.makedirs(frame_dir)
    async with Recorder(site, out, width=W, height=H) as s:
        task = asyncio.ensure_future(s.capture_loop(frame_dir))
        try:
            await tour(s)
        finally:
            task.cancel()
        frames, cuts, errors = s.frames, s.cuts, s.errors()
    mp4 = encode(out, frames)
    final = os.path.join(out, 'coco_lab3_demo.mp4')
    os.replace(mp4, final)
    span = frames[-1][1] - frames[0][1]
    with open(os.path.join(out, 'cuts.json'), 'w') as f:
        json.dump({'frames': len(frames), 'video_s': round(span, 2),
                   'capture_fps': round(len(frames) / span, 2), 'cuts': cuts,
                   'console_errors': errors, 'site': site}, f, indent=1)
    print(json.dumps({'video': final, 'frames': len(frames), 'video_s': round(span, 2),
                      'cuts': cuts, 'console_errors': errors}))


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1:]))
