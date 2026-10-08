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
Record Lab 4's demo video in headless Firefox (viewport only).

The same recorder as Labs 1-3 (``record_demo.py``: viewport frames at their
real timestamps, captions as a fixed strip, cuts listed in ``cuts.json``).
The one-time Pyodide start-up is run before recording; every coco_lab run
shown afterwards is recorded, and its wait is CUT and listed.

Usage::

    python3 lab_web/tools/browser/record_lab4_demo.py <site-url> <outdir>
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


async def set_truth(s, value):
    await s.js("(() => { const e = document.querySelector('[data-testid=search-truth-pick]');"
               " const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
               f" set.call(e, {json.dumps(value)}); e.dispatchEvent(new Event('change', {{ bubbles: true }}));"
               " return 1; })()")


async def tour(s):
    site = s.site
    # warm up Pyodide off camera
    await s.open('?view=search')
    await s.wait(check.SEARCH_READY, timeout=120)
    t_warm = time.monotonic()
    await check.click_testid(s, 'search-order-bay_1')
    await check.click_testid(s, 'search-pred-mine')
    await check.click_testid(s, 'search-run')
    await s.wait(check.SEARCH_DONE, timeout=900, every=0.2)
    await s.open('?view=search')
    await s.wait(check.SEARCH_READY, timeout=120)
    await asyncio.sleep(1.0)
    await top(s)
    s.cuts.append({'what': 'before recording: the one-time Pyodide start-up and a warm-up run',
                   'seconds_cut': round(time.monotonic() - t_warm, 2), 'at_video_s': 0.0})

    s.recording = True
    await s.caption('COCO Lab 4 — Search. The robot is told "red". Not where it is.')
    await hold(4.5)
    await s.caption('It knows its map, the four bays, what each costs to reach and climb — and believes nothing yet')
    await hold(4.5)
    await center(s, 'search-default-plan')
    await s.caption("coco_lab's plan, before any look: every order costed, the cheapest expected search")
    await hold(5.0)
    await top(s)
    await s.caption('Your turn: choose the order you would search in')
    for bay in ('bay_1', 'bay_2', 'bay_3', 'bay_4'):
        await check.click_testid(s, f'search-order-{bay}')
        await hold(0.6)
    await center(s, 'search-my-order')
    await hold(2.0)
    await s.caption('Predict: whose order has the lower EXPECTED search cost?')
    await check.click_testid(s, 'search-pred-mine')
    await hold(2.0)
    await s.caption('Place the target where the robot will find it LAST: Bay 1')
    await set_truth(s, '0')
    await hold(2.0)
    await check.click_testid(s, 'search-run')
    await s.cut('coco_lab running both searches in the browser (Pyodide)',
                s.wait(check.SEARCH_DONE, timeout=600, every=0.1))
    await center(s, 'search-revealed')
    await s.caption("Reveal: the robot's order is cheaper on average — and on THIS placement yours wins")
    await hold(7.0)
    await top(s)
    await s.caption('Watch the robot: Bay 3, not there. Bay 4, not there. Bay 2, not there...')
    await check.click_testid(s, 'search-play')
    await hold(9.0)
    await s.caption('Each miss moves the belief to the other bays (Bayes); a searched bay keeps a little: d = 0.9')
    await center(s, 'search-belief-table')
    await hold(6.0)
    await check.click_testid(s, 'search-end')
    await top(s)
    await s.caption('...found in Bay 1. Negative search: A, B, C, then D.')
    await hold(5.0)
    await center(s, 'search-outcomes')
    await s.caption('Same placement, same seed, every policy: only the order differs')
    await hold(6.0)
    await top(s)
    await s.caption('The full ROS 2 stack (simulated), in Gazebo: told only the colour, '
                    'searching with the same coco_lab code')
    await check.click_testid(s, 'search-sub-replay')
    await s.wait(check.SEARCH_READY, timeout=60)
    await top(s)
    await hold(4.0)
    await check.click_testid(s, 'search-replay-play')
    await hold(8.0)
    await check.click_testid(s, 'search-replay-end')
    await s.caption("The mission's state machine as it ran, in simulator seconds")
    await center(s, 'search-timeline')
    await hold(6.0)
    await s.caption('The truth comes from the manifest — the evaluator. The robot never had it.')
    await check.click_testid(s, 'search-replay-truth')
    await top(s)
    await hold(5.0)
    await s.caption('What is proven, and where: every claim names its test; the Gazebo matrix, measured')
    await check.click_testid(s, 'search-sub-evidence')
    await top(s)
    await hold(4.0)
    await center(s, 'search-matrix')
    await hold(7.0)
    await s.caption(f'Try it: {site}?view=search')
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
    final = os.path.join(out, 'coco_lab4_demo.mp4')
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
