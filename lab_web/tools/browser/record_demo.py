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
Record Lab 1's demo video from the live site, in headless Firefox.

Only the browser VIEWPORT is captured (``browsingContext.captureScreenshot``)
-- never the desktop, a terminal or another window. Frames are taken
continuously while a scripted tour runs, each with its real timestamp, and
``ffmpeg`` encodes them at their real pacing. The one-time Pyodide start-up
is done before recording starts, and the waits that are cut are listed in
``cuts.json`` beside the video, so the release notes can say exactly what
was cut. Captions are added to the page by this script, as a fixed strip;
they are not part of the site.

Usage::

    python3 lab_web/tools/browser/record_demo.py <site-url> <outdir> [--probe]

``--probe`` takes one frame and measures the frame rate, then stops: look
at ``probe.png`` before recording. Writes ``<outdir>/frames/``,
``frames.txt``, ``cuts.json`` and ``coco_lab1_demo.mp4``.
"""

import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check  # noqa: E402  (the harness: launch, Session, helpers)
from bidi import Bidi  # noqa: E402

W, H = 1400, 1150  # CSS px; at DPR 0.8 the frames are 1120 x 920
DPR = 0.8


class DispatchBidi(Bidi):
    """Bidi with one reader task, so frames and actions can interleave."""

    async def start(self):
        self.pending = {}
        self.reader = asyncio.ensure_future(self._read())

    async def _read(self):
        while True:
            raw = await self.ws.read_message()
            if raw is None:
                for f in self.pending.values():
                    f.set_exception(RuntimeError('bidi socket closed'))
                return
            msg = json.loads(raw)
            f = self.pending.pop(msg.get('id'), None)
            if f is None:
                self.events.append(msg)
            elif msg.get('type') == 'error':
                f.set_exception(RuntimeError(f"{msg.get('error')}: {msg.get('message')}"))
            else:
                f.set_result(msg.get('result'))

    async def cmd(self, method, **params):
        self.n += 1
        my = self.n
        fut = asyncio.get_event_loop().create_future()
        self.pending[my] = fut
        await self.ws.write_message(json.dumps({'id': my, 'method': method, 'params': params}))
        return await fut


class Recorder(check.Session):
    async def __aenter__(self):
        self.proc = check.launch(self.width, self.height, self.reduced)
        base = await Bidi.connect(port=check.PORT)
        self.b = DispatchBidi(base.ws)
        await self.b.start()
        await self.b.cmd('session.new', capabilities={})
        await self.b.cmd('session.subscribe', events=['log.entryAdded'])
        tree = await self.b.cmd('browsingContext.getTree')
        self.ctx = tree['contexts'][0]['context']
        await self.b.cmd('browsingContext.setViewport', context=self.ctx,
                         viewport={'width': self.width, 'height': self.height}, devicePixelRatio=DPR)
        self.frames, self.cuts, self.recording, self.t_cut = [], [], False, 0.0
        return self

    async def grab(self, path):
        r = await self.b.cmd('browsingContext.captureScreenshot', context=self.ctx)
        with open(path, 'wb') as f:
            f.write(base64.b64decode(r['data']))

    async def capture_loop(self, frame_dir):
        while True:
            if self.recording:
                t = time.monotonic() - self.t_cut
                path = os.path.join(frame_dir, f'{len(self.frames):05d}.png')
                await self.grab(path)
                self.frames.append((path, t))
            else:
                await asyncio.sleep(0.02)

    async def cut(self, what, coro):
        """Run ``coro`` off camera; the video jumps over it (listed in cuts.json)."""
        self.recording = False
        t0 = time.monotonic()
        result = await coro
        dt = time.monotonic() - t0
        # frame times are on the monotonic clock; the cut is placed in VIDEO time
        at = self.frames[-1][1] - self.frames[0][1] if self.frames else 0.0
        self.cuts.append({'what': what, 'seconds_cut': round(dt, 2), 'at_video_s': round(at, 2)})
        self.t_cut += dt
        self.recording = True
        return result

    async def caption(self, text):
        await self.js(
            "(() => { let c = document.getElementById('demo-caption'); if (!c) { c = document.createElement('div');"
            " c.id = 'demo-caption'; c.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:9999;"
            "padding:10px 16px;background:rgba(20,20,18,0.88);color:#fff;font:600 18px system-ui,sans-serif;"
            "text-align:center;pointer-events:none'; document.body.appendChild(c); }"
            f" c.textContent = {json.dumps(text)}; return 1; }})()")


async def hold(seconds):
    await asyncio.sleep(seconds)


async def pick(s, bundle_id):
    """Select a catalog bundle in the picker, as a change event."""
    await s.js("(() => { const e = document.querySelector('[data-testid=picker]');"
               " const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
               f" set.call(e, {json.dumps(bundle_id)}); e.dispatchEvent(new Event('change', {{ bubbles: true }}));"
               " return 1; })()")


async def tour(s):
    site = s.site
    await s.open('?perf&bundle=astar_open')
    await s.wait(check.READY, timeout=90)
    # off camera: start Pyodide once, so no scene waits for it
    t_warm = time.monotonic()
    await click(s, 'set-conn-4')
    await click(s, 'run-settings')
    await s.wait(check.STATUS_SETTLED, timeout=300, every=0.2)
    await click(s, 'rung-1')
    await s.wait("document.querySelector('[data-testid=picker]').value === 'astar_open'", timeout=60)
    await asyncio.sleep(1.0)
    await s.js('window.scrollTo(0, 0), 1')
    s.cuts.append({'what': "before recording: the one-time Pyodide start-up and a warm-up search (the page's "
                           "status line says 'Loading Python…' while it runs)",
                   'seconds_cut': round(time.monotonic() - t_warm, 2), 'at_video_s': 0.0})

    s.recording = True
    await s.caption('COCO Lab 1 — Plan: graph search, traced event by event, computed by coco_lab')
    await hold(3.0)
    await click(s, 'play')
    await s.js('window.scrollTo(0, 0), 1')
    await hold(4.0)

    await s.caption('Paint walls: coco_lab reruns the search in your browser (Python via Pyodide)')
    await click(s, 'tool-paint')
    await s.js("(() => { const e = document.querySelector('[data-testid=brush]');"
               " const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
               " set.call(e, '3'); e.dispatchEvent(new Event('change', { bubbles: true })); return 1; })()")
    await s.js('window.scrollTo(0, 0), 1')
    await check.drag_cells(s, [(4, 10), (8, 10), (12, 10)], 20, 20)
    await s.wait(check.STATUS_SETTLED, timeout=60, every=0.1)
    await s.js('window.scrollTo(0, 0), 1')
    await hold(4.0)
    await click(s, 'tool-erase')
    await s.js('window.scrollTo(0, 0), 1')
    await check.drag_cells(s, [(8, 10), (9, 10)], 20, 20)
    await s.wait(check.STATUS_SETTLED, timeout=60, every=0.1)
    await s.js('window.scrollTo(0, 0), 1')
    await hold(4.0)

    await s.caption('Race: four algorithms, identical inputs — predict first, then watch')
    for a in ('bfs', 'greedy'):
        await click(s, f'race-{a}')
    await click(s, 'predict-fewest-astar')
    await hold(1.0)
    await click(s, 'race-start')
    await s.wait("document.querySelector('[data-testid=race-table]')", timeout=60)
    await s.js("(document.querySelector('[data-testid=race]').scrollIntoView({block: 'start'}), 1)")
    await s.js("(() => { const e = document.querySelector('.race .speed select');"
               " const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
               " set.call(e, '1'); e.dispatchEvent(new Event('change', { bubbles: true })); return 1; })()")
    await s.js("(() => { const p = document.querySelector('.race [data-testid=play]'); p.click(); return 1; })()")
    await hold(7.0)
    await s.js("(document.querySelector('[data-testid=race-table]').scrollIntoView({block: 'center'}), 1)")
    await hold(4.0)
    await click(s, 'race-close')

    await s.caption("Map ladder: up to Nav2's own inflated costmap, with COCO's footprint swept along the path")
    await click(s, 'rung-3')
    await s.wait("document.querySelector('[data-testid=picker]').value === 'costmap_0_10m'", timeout=60)
    await s.js('window.scrollTo(0, 0), 1')
    await hold(5.0)

    await s.caption('A real run: planned by coco_lab, driven by Nav2 — ground truth, AMCL belief, plan')
    await pick(s, 'lab1c_astar')
    await s.wait("document.querySelector('[data-testid=tracking-plot]')", timeout=60)
    await s.js('window.scrollTo(0, 0), 1')
    await s.js("(() => { const e = document.querySelector('.player .speed select');"
               " const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
               " set.call(e, '100'); e.dispatchEvent(new Event('change', { bubbles: true })); return 1; })()")
    await click(s, 'play')
    await s.js('window.scrollTo(0, 0), 1')
    await hold(7.0)
    await s.caption('Tracking error, ground truth to the plan: 1C’s own numbers, plotted')
    await s.js("(document.querySelector('[data-testid=tracking]').scrollIntoView({block: 'start'}), 1)")
    b = await check.box_of(s, 'tracking-plot')
    for i in range(1, 25):
        await s.b.cmd('input.performActions', context=s.ctx, actions=[{
            'type': 'pointer', 'id': 'mouse', 'parameters': {'pointerType': 'mouse'},
            'actions': [{'type': 'pointerMove', 'x': int(b[0] + b[2] * (0.08 + 0.033 * i)),
                         'y': int(b[1] + b[3] / 2), 'duration': 120}]}])
    await hold(1.0)

    await s.caption('The exhibit: “The A* myth, twice” — A* and Dijkstra, same cost')
    await click(s, 'view-exhibit')
    await s.wait("document.querySelector('[data-testid=exhibit-run]')", timeout=30)
    await s.js('window.scrollTo(0, 0), 1')
    await hold(2.0)
    await click(s, 'exhibit-run')
    await s.wait("document.querySelector('[data-testid=exhibit-a-verdict]')", timeout=60)
    await s.js("(document.querySelector('[data-testid=exhibit-a-verdict]').scrollIntoView({block: 'start'}), 1)")
    await hold(4.0)
    await s.caption("COCO's 6.2 %: two planners' implementations — and what 1C measured instead")
    await s.js("(document.querySelector('[data-testid=exhibit-b]').scrollIntoView({block: 'start'}), 1)")
    await hold(4.5)
    await s.caption('The ISRO “4 %”: a reconstruction, not reproduced on fixed inputs')
    await s.js("(document.querySelector('[data-testid=exhibit-c]').scrollIntoView({block: 'start'}), 1)")
    await hold(4.0)
    await s.caption(f'Try it: {site}')
    await hold(3.0)
    s.recording = False
    await asyncio.sleep(0.3)


async def click(s, testid):
    await check.click_testid(s, testid)


def encode(out, frames):
    lst = os.path.join(out, 'frames.txt')
    with open(lst, 'w') as f:
        for (path, t), nxt in zip(frames, frames[1:] + [(None, frames[-1][1] + 1.0)]):
            f.write(f"file '{os.path.abspath(path)}'\nduration {max(0.001, nxt[1] - t):.4f}\n")
        f.write(f"file '{os.path.abspath(frames[-1][0])}'\n")
    mp4 = os.path.join(out, 'coco_lab1_demo.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
                    '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'slow', '-crf', '22',
                    '-movflags', '+faststart', mp4], check=True)
    return mp4


async def main(argv):
    site, out = argv[0], argv[1]
    probe = '--probe' in argv
    os.makedirs(out, exist_ok=True)
    frame_dir = os.path.join(out, 'frames')
    shutil.rmtree(frame_dir, ignore_errors=True)
    os.makedirs(frame_dir)
    async with Recorder(site, out, width=W, height=H) as s:
        if probe:
            await s.open('?bundle=astar_open')
            await s.wait("document.querySelector('[data-testid=map-canvas]')", timeout=90)
            await asyncio.sleep(1.0)
            t0 = time.monotonic()
            for i in range(20):
                await s.grab(os.path.join(frame_dir, f'probe_{i:02d}.png'))
            fps = 20 / (time.monotonic() - t0)
            shutil.copy(os.path.join(frame_dir, 'probe_00.png'), os.path.join(out, 'probe.png'))
            shutil.rmtree(frame_dir)
            print(json.dumps({'probe': os.path.join(out, 'probe.png'), 'capture_fps': round(fps, 2),
                              'viewport_css': [W, H], 'device_pixel_ratio': DPR}))
            return
        task = asyncio.ensure_future(s.capture_loop(frame_dir))
        try:
            await tour(s)
        finally:
            task.cancel()
        frames, cuts, errors = s.frames, s.cuts, s.errors()
    mp4 = encode(out, frames)
    span = frames[-1][1] - frames[0][1]
    with open(os.path.join(out, 'cuts.json'), 'w') as f:
        json.dump({'frames': len(frames), 'video_s': round(span, 2), 'capture_fps': round(len(frames) / span, 2),
                   'cuts': cuts, 'console_errors': errors, 'site': site}, f, indent=1)
    print(json.dumps({'video': mp4, 'frames': len(frames), 'video_s': round(span, 2), 'cuts': cuts,
                      'console_errors': errors}))


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1:]))
