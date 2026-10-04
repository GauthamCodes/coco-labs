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
Record Lab 2's demo video in headless Firefox (viewport only).

The same recorder as Lab 1 (``record_demo.py``: viewport frames at their
real timestamps, captions as a fixed strip added by this script, cuts
listed in ``cuts.json``). The one-time Pyodide start-up is run before
recording. ``cuts.json`` also records which site was recorded: the public
URL, or a local build and its commit.

Usage::

    python3 lab_web/tools/browser/record_lab2_demo.py <site-url> <outdir>
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

DONE = check.LOC_DONE


async def set_range(s, aria, value):
    """Set a React-controlled range input like a user drag would."""
    await s.js("(() => { const e = document.querySelector(" + json.dumps(f'input[aria-label="{aria}"]') + ");"
               " const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;"
               f" set.call(e, {json.dumps(str(value))}); e.dispatchEvent(new Event('input', {{ bubbles: true }}));"
               " e.dispatchEvent(new Event('change', { bubbles: true })); return 1; })()")


async def set_select(s, testid, value):
    await s.js(f"(() => {{ const e = document.querySelector('[data-testid={testid}]');"
               " const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
               f" set.call(e, {json.dumps(value)}); e.dispatchEvent(new Event('change', {{ bubbles: true }}));"
               " return 1; })()")


async def top(s):
    await s.js('window.scrollTo(0, 0), 1')


async def tour(s):
    site = s.site
    await s.open('?view=localise&scene=loc_kidnap')
    await s.wait(check.LOC_READY, timeout=90)
    # off camera: Pyodide's one-time start, so no scene waits for it
    t_warm = time.monotonic()
    await check.click_testid(s, 'loc-run')
    await s.wait(DONE, timeout=600, every=0.2)
    await s.open('?view=localise&scene=loc_kidnap')
    await s.wait(check.LOC_READY, timeout=90)
    await asyncio.sleep(1.0)
    await top(s)
    s.cuts.append({'what': "before recording: the one-time Pyodide start-up and a warm-up run",
                   'seconds_cut': round(time.monotonic() - t_warm, 2), 'at_video_s': 0.0})

    s.recording = True
    await s.caption('COCO Lab 2 — Localise. Sketch: coco_lab\'s 2D model of COCO, not the robot')
    await hold(3.5)
    await s.caption('Measured against Gazebo at 237 identical poses — shown beside the mode, with its evidence')
    await s.js("(() => { const d = document.querySelector('[data-testid=loc-fidelity]'); d.open = true;"
               " d.scrollIntoView({block: 'start'}); return 1; })()")
    await hold(4.5)
    await s.js("(() => { document.querySelector('[data-testid=loc-fidelity]').open = false; return 1; })()")
    await top(s)
    await s.caption('Predict first: will each filter find the robot after it is carried 9.2 m?')
    radios = await s.js("document.querySelectorAll('.predict input[type=radio]').length")
    for i, ans in zip(range(0, int(radios), 2), (0, 1, 1)):
        b = await s.js(f"(() => {{ const e = document.querySelectorAll('.predict input[type=radio]')[{i + ans}];"
                       " e.scrollIntoView({block: 'center'}); const r = e.getBoundingClientRect();"
                       " return [r.left, r.top, r.width, r.height]; })()")
        await s.b.click(s.ctx, b[0] + b[2] / 2, b[1] + b[3] / 2)
        await hold(0.6)
    await top(s)
    await s.caption('Play: particles (orange), EKF ellipse (green), the truth (blue), the scan at the belief')
    await s.js("(() => { const e = document.querySelector('select[aria-label=\"Playback speed\"]');"
               " const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
               " set.call(e, '8'); e.dispatchEvent(new Event('change', { bubbles: true })); return 1; })()")
    await check.click_testid(s, 'loc-play')
    await top(s)
    await hold(9.0)
    await s.caption('Hide the truth: this is all the robot knows. Scan endpoints off the walls = lost')
    await check.click_testid(s, 'loc-truth')
    await top(s)
    await hold(5.0)
    await check.click_testid(s, 'loc-truth')
    await s.caption('Reveal: coco_lab\'s outcome, and how often it happens over 20 seeds')
    await check.click_testid(s, 'loc-reveal')
    await s.js("(document.querySelector('[data-testid=loc-revealed]').scrollIntoView({block: 'center'}), 1)")
    await hold(6.0)
    await top(s)
    await s.caption('Race: one map per filter — same world, same odometry, same scans')
    await check.click_testid(s, 'loc-race-toggle')
    await top(s)
    await hold(5.0)
    await check.click_testid(s, 'loc-race-toggle')
    await s.caption('Change it: 1,000 particles — coco_lab reruns the world and every filter in your browser')
    await set_range(s, 'Particles', 1000)
    await check.click_testid(s, 'loc-run')
    await s.wait(DONE, timeout=300, every=0.1)
    await top(s)
    await hold(5.0)
    await s.caption('Kidnap it yourself: pick where the robot is carried — click the map')
    btn = await s.js("(() => { const b = [...document.querySelectorAll('button')]"
                     ".find((x) => /^to \\(/.test(x.textContent)); b.scrollIntoView({block: 'center'});"
                     " const r = b.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
    await s.b.click(s.ctx, btn[0] + btn[2] / 2, btn[1] + btn[3] / 2)
    await hold(1.0)
    cb = await check.box_of(s, 'loc-canvas')
    await s.b.click(s.ctx, cb[0] + cb[2] * 4.0 / 12.0, cb[1] + cb[3] * (1 - 4.0 / 8.0))
    await hold(1.0)
    await check.click_testid(s, 'loc-run')
    await s.wait(DONE, timeout=300, every=0.1)
    await top(s)
    await hold(6.0)
    await s.caption("COCO's real localisation failures, each with its evidence")
    await check.click_testid(s, 'loc-sub-exhibits')
    await s.wait("document.querySelector('[data-testid=exhibit-covariance] svg')", timeout=30)
    await top(s)
    await hold(3.0)
    for sec, cap in (('exhibit-recovery-alpha', 'Injection off: AMCL cannot leave a pose it is sure of — and the A/B'),
                     ('exhibit-covariance', "AMCL's covariance moved the wrong way at a 3 m divergence"),
                     ('exhibit-run15', 'Run 15, and what an EKF with the gyro does to the odometry')):
        await s.caption(cap)
        await s.js(f"(document.querySelector('[data-testid={sec}]').scrollIntoView({{block: 'start'}}), 1)")
        await hold(5.0)
    await s.caption(f'Try it: {site}?view=localise')
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
    final = os.path.join(out, 'coco_lab2_demo.mp4')
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
