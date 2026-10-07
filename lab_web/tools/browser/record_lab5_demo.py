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
Record Lab 5's demo video in headless Firefox (viewport only).

The same recorder as Labs 1-4 (``record_demo.py``: viewport frames at their
real timestamps, captions as a fixed strip, cuts listed in ``cuts.json``).
The one-time Pyodide start-up is run before recording; the coco_lab run
shown afterwards is recorded, and its wait is CUT and listed.

Usage::

    python3 lab_web/tools/browser/record_lab5_demo.py <site-url> <outdir>
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


async def top(s):
    await s.js('window.scrollTo(0, 0), 1')


async def center(s, testid):
    await s.js(f"(document.querySelector('[data-testid={testid}]').scrollIntoView({{block: 'center'}}), 1)")


async def scrub(s, frac):
    await s.js(check.SET_RANGE.format('move-drive-scrub', frac))


async def pick_select(s, testid, value):
    await s.js(f"(() => {{ const e = document.querySelector('[data-testid={testid}]');"
               " const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
               f" set.call(e, {json.dumps(value)}); e.dispatchEvent(new Event('change', {{ bubbles: true }}));"
               " return 1; })()")


async def sweep(s, start, end, seconds, steps=40):
    for k in range(steps + 1):
        await scrub(s, start + (end - start) * k / steps)
        await hold(seconds / steps)


async def tour(s):
    site = s.site
    # warm up Pyodide off camera
    await s.open('?view=move')
    await s.wait(check.MOVE_MAP, timeout=120)
    t_warm = time.monotonic()
    await check.click_testid(s, 'move-sub-replan')
    await s.wait(check.MOVE_GRID, timeout=60)
    await check.click_testid(s, 'move-replan-run')
    await s.wait(check.MOVE_DONE, timeout=900, every=0.2)
    await s.open('?view=move')
    await s.wait(check.MOVE_MAP, timeout=120)
    await asyncio.sleep(1.0)
    await top(s)
    s.cuts.append({'what': 'before recording: the one-time Pyodide start-up and a warm-up run',
                   'seconds_cut': round(time.monotonic() - t_warm, 2), 'at_video_s': 0.0})

    s.recording = True
    await s.caption('COCO Lab 5 — Move. A path is not a motion.')
    await hold(4.0)
    await center(s, 'move-chain')
    await s.caption('The global planner draws the line once; a local controller drives it ten times a second')
    await hold(5.0)
    await center(s, 'move-map')
    await s.caption('One frozen path, three Nav2 controllers, the same robot limits. Watch DWB first.')
    await hold(3.0)
    await sweep(s, 0.0, 0.85, 9.0)
    await s.caption("DWB scores 819 candidate motions each cycle — and stalls before the hairpin. 0 of 5 runs got round.")
    await hold(4.0)
    await pick_select(s, 'move-focus', 'MPPI_1')
    await asyncio.sleep(0.5)
    await s.caption('MPPI: thousands of sampled rollouts, averaged. It gets round by cutting the corner.')
    await sweep(s, 0.4, 0.75, 7.0)
    await pick_select(s, 'move-focus', 'RPP_1')
    await asyncio.sleep(0.5)
    await s.caption('Regulated Pure Pursuit: chase a point 0.6 m ahead. Closest to the line.')
    await sweep(s, 0.4, 0.75, 6.0)
    await s.caption('Predict, then see what was measured: 5 runs each, fresh simulator each')
    await check.click_testid(s, 'move-pred-RPP')
    await check.click_testid(s, 'move-reveal')
    await center(s, 'move-table')
    await hold(7.0)
    await top(s)
    await s.caption('People on the apron: the global path knows nothing about them')
    await check.click_testid(s, 'move-sub-people')
    await s.wait(check.MOVE_MAP, timeout=60)
    await center(s, 'move-map')
    await sweep(s, 0.2, 0.75, 8.0)
    await s.caption('Walking straight at the robot: nobody swerved. It stopped; the (ghost) person walked into it.')
    await top(s)
    await check.click_testid(s, 'move-scenario-oncoming')
    await s.wait(check.MOVE_MAP, timeout=60)
    await center(s, 'move-map')
    await sweep(s, 0.3, 0.8, 8.0)
    await top(s)
    await s.caption('Run 15: the robot believed it was 3.4 m from where it was. "No valid trajectories out of 819!"')
    await check.click_testid(s, 'move-sub-run15')
    await asyncio.sleep(1.5)
    await top(s)
    await hold(5.0)
    await center(s, 'move-run15-verdict')
    await s.caption('Reproduced here: the mechanism, not the log line — every controller refused the path at once')
    await hold(7.0)
    await top(s)
    await s.caption('When the map is wrong: D* Lite repairs the plan as the robot sees what its map lacked')
    await check.click_testid(s, 'move-sub-replan')
    await s.wait(check.MOVE_GRID, timeout=60)
    await center(s, 'move-replan-grid')
    await check.click_testid(s, 'move-replan-play')
    await hold(11.0)
    await s.caption('Paint obstacles the robot does not know about, and coco_lab runs it again in your browser')
    b = await check.box_of(s, 'move-replan-grid')
    for r, c in ((9, 14), (10, 14), (11, 14)):
        await s.b.click(s.ctx, b[0] + b[2] * (c + 0.5) / 32, b[1] + b[3] * (r + 0.5) / 20)
        await hold(0.5)
    await check.click_testid(s, 'move-replan-run')
    await s.cut('coco_lab running the D* Lite episode in the browser (Pyodide)',
                s.wait(check.MOVE_DONE, timeout=600, every=0.1))
    await center(s, 'move-replan-grid')
    await check.click_testid(s, 'move-replan-play')
    await hold(9.0)
    await center(s, 'move-rounds')
    await s.caption('Every replan: the same cost as A* from scratch — and sometimes MORE work, measured')
    await hold(7.0)
    await top(s)
    await s.caption('What is proven, and where: every claim names its test or measurement')
    await check.click_testid(s, 'move-sub-evidence')
    await top(s)
    await hold(6.0)
    await s.caption(f'Try it: {site}?view=move')
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
    final = os.path.join(out, 'coco_lab5_demo.mp4')
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
