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
Drive lab_web in headless Firefox (WebDriver BiDi) and measure it.

Reuses ``scripts/browser_check/bidi.py`` (tornado; no Selenium, no driver,
no extension). Every interaction is a real key press or pointer click on
the built site. The numbers are HEADLESS Firefox numbers on this machine;
a headed browser may differ, and they are not extrapolated.

Usage::

    python3 lab_web/tools/browser/check.py <site-url> <outdir> [scenario...]

``<site-url>`` is the site root, e.g.
``http://127.0.0.1:4173/coco-robot-jazzy-2.0/``. Scenarios: ``smoke``
(every catalog bundle loads and draws), ``player`` (keyboard, scrub,
play), ``reduced`` (prefers-reduced-motion), ``fps`` (full-arena Dijkstra
playback), ``phone`` (390 x 844), ``edit`` (Pyodide cold and warm: one
painted cell to its first frame), ``weight`` (initial page weight), ``lab``
(Lab 1.1: settings, painting, a race, the map ladder). Default: all. Writes ``report.json`` and
screenshots into ``<outdir>``.
"""

import asyncio
import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'scripts', 'browser_check'))
from bidi import Bidi  # noqa: E402

PORT = 9226


def launch(width, height, reduced_motion=False):
    """Start headless Firefox on a FRESH profile (under $HOME: snap)."""
    prof = os.path.expanduser(f'~/coco_ff_profile_{PORT}')
    shutil.rmtree(prof, ignore_errors=True)
    os.makedirs(prof)
    prefs = ['user_pref("ui.prefersReducedMotion", %d);' % (1 if reduced_motion else 0),
             'user_pref("browser.cache.disk.enable", false);',
             'user_pref("app.update.enabled", false);',
             'user_pref("datareporting.policy.dataSubmissionEnabled", false);']
    with open(os.path.join(prof, 'user.js'), 'w') as f:
        f.write('\n'.join(prefs) + '\n')
    log = open(os.path.join(HERE, 'firefox.log'), 'w')
    return subprocess.Popen(
        ['firefox', '--headless', '--no-remote', '--profile', prof,
         f'--remote-debugging-port={PORT}', f'--window-size={width},{height}',
         'about:blank'],
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


class Session:
    def __init__(self, site, out, width=1400, height=1000, reduced=False):
        self.site, self.out = site, out
        self.width, self.height, self.reduced = width, height, reduced

    async def __aenter__(self):
        self.proc = launch(self.width, self.height, self.reduced)
        self.b = await Bidi.connect(port=PORT)
        await self.b.cmd('session.new', capabilities={})
        await self.b.cmd('session.subscribe', events=[
            'log.entryAdded', 'network.beforeRequestSent', 'network.responseCompleted'])
        tree = await self.b.cmd('browsingContext.getTree')
        self.ctx = tree['contexts'][0]['context']
        await self.b.cmd('browsingContext.setViewport', context=self.ctx,
                         viewport={'width': self.width, 'height': self.height})
        return self

    async def __aexit__(self, *exc):
        try:
            await self.b.cmd('session.end')
        except Exception:
            pass
        os.killpg(self.proc.pid, signal.SIGTERM)
        await asyncio.sleep(0.5)

    async def open(self, query=''):
        await self.b.cmd('browsingContext.navigate', context=self.ctx,
                         url=self.site + query, wait='complete')

    async def js(self, expr):
        return await self.b.eval(self.ctx, expr)

    async def wait(self, expr, timeout=60.0, every=0.1):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                v = await self.js(expr)
            except RuntimeError:
                v = None
            if v:
                return v
            await asyncio.sleep(every)
        raise TimeoutError(expr)

    async def shot(self, name):
        path = os.path.join(self.out, f'{name}.png')
        await self.b.shot(self.ctx, path)
        return path

    async def key(self, value, shift=False):
        acts = []
        if shift:
            acts.append({'type': 'keyDown', 'value': ''})
        acts += [{'type': 'keyDown', 'value': value}, {'type': 'keyUp', 'value': value}]
        if shift:
            acts.append({'type': 'keyUp', 'value': ''})
        await self.b.keys(self.ctx, acts)

    def requests(self):
        return [e['params']['request']['url'] for e in self.b.events
                if e.get('method') == 'network.beforeRequestSent']

    def errors(self):
        out = []
        for e in self.b.events:
            if e.get('method') == 'log.entryAdded':
                p = e['params']
                if p.get('level') in ('error', 'warn'):
                    out.append(p.get('text'))
        return out


READY = ("(() => { const c = document.querySelector('[data-testid=map-canvas]');"
         " return !!(c && c.width > 0 && window.__cocoLabPerf &&"
         " window.__cocoLabPerf.marks['bundle-first-frame']); })()")
STATE = """(() => {
  const t = (s) => { const e = document.querySelector(s); return e ? e.textContent.trim() : null; };
  const scrub = document.querySelector('[data-testid=scrub]');
  return { badge: t('[data-testid=mode-badge]'), error: t('[data-testid=error]'),
    k: scrub ? Number(scrub.value) : null, n: scrub ? Number(scrub.max) : null,
    play: t('[data-testid=play]'), pos: t('.player-pos'),
    reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
    cookie: document.cookie, storage: localStorage.length + sessionStorage.length };
})()"""


async def catalog(s):
    return await s.js(f"fetch('{s.site}generated/catalog.json').then(r => r.json())")


async def reset_perf(s):
    await s.js("(() => { const p = window.__cocoLabPerf; p.frames.length = 0;"
               " p.frameTimes.length = 0; p.marks = {}; return 1; })()")


async def box_of(s, testid):
    """[left, top, width, height] of an element, scrolled into view."""
    return await s.js(
        f"(() => {{ const e = document.querySelector('[data-testid={testid}]');"
        " e.scrollIntoView({block: 'center'}); const r = e.getBoundingClientRect();"
        " return [r.left, r.top, r.width, r.height]; })()")


async def click_testid(s, testid):
    """A real pointer click on the centre of an element."""
    b = await box_of(s, testid)
    await s.b.click(s.ctx, b[0] + b[2] / 2, b[1] + b[3] / 2)


async def focus_testid(s, testid):
    await s.js(f"(document.querySelector('[data-testid={testid}]').focus(), 1)")


async def drag_cells(s, cells, w, h):
    """A real pointer drag through map cells [(row, col), ...]."""
    b = await box_of(s, 'map-canvas')
    pts = [(b[0] + b[2] * (c + 0.5) / w, b[1] + b[3] * (r + 0.5) / h) for r, c in cells]
    acts = [{'type': 'pointerMove', 'x': int(pts[0][0]), 'y': int(pts[0][1])},
            {'type': 'pointerDown', 'button': 0}]
    for x, y in pts[1:]:
        acts += [{'type': 'pointerMove', 'x': int(x), 'y': int(y), 'duration': 30}]
    acts += [{'type': 'pointerUp', 'button': 0}]
    await s.b.cmd('input.performActions', context=s.ctx, actions=[{
        'type': 'pointer', 'id': 'mouse', 'parameters': {'pointerType': 'mouse'},
        'actions': acts}])


STATUS_SETTLED = ("(() => { const e = document.querySelector('[data-testid=edit-status]');"
                  " return e && !e.classList.contains('busy') ? e.className : null; })()")
TEXT = "(() => {{ const e = document.querySelector('[data-testid={}]'); return e ? e.innerText : null; }})()"


# -- scenarios -------------------------------------------------------------------

async def smoke(site, out):
    """Every catalog bundle loads, validates against the catalog and draws."""
    res = []
    async with Session(site, out) as s:
        await s.open('?perf')
        await s.wait(READY)
        cat = await catalog(s)
        for e in cat['bundles']:
            await s.open(f"?perf&bundle={e['id']}")
            t0 = time.time()
            await s.wait(READY, timeout=90)
            st = await s.js(STATE)
            await s.js("(() => { [...document.querySelectorAll('[role=tab]')]"
                       ".find(b => b.textContent === 'recording').click(); return 1; })()")
            await asyncio.sleep(0.3)
            rec = await s.js("(() => { const p = document.querySelector('[data-testid=recording-panel]');"
                             " return p ? p.innerText : null; })()")
            await s.shot(f"smoke_{e['id']}")
            res.append({'id': e['id'], 'source_kind': e['source_kind'], 'badge': st['badge'],
                        'error': st['error'], 'n': st['n'], 'k': st['k'],
                        'load_to_first_frame_s': round(time.time() - t0, 3),
                        'recording_panel': rec})
        return {'bundles': res, 'console_errors': s.errors(), 'cookie': st['cookie'],
                'storage_items': st['storage']}


async def player(site, out):
    """Space, arrows, Shift+arrows, scrub and play, by real key presses."""
    async with Session(site, out) as s:
        await s.open('?perf&bundle=astar_open')
        await s.wait(READY)
        seq = []
        st = await s.js(STATE)
        seq.append(('loaded', st['k'], st['n']))
        await s.key('')                      # ArrowLeft
        seq.append(('left', (await s.js(STATE))['k']))
        await s.key('', shift=True)          # Shift+ArrowLeft
        seq.append(('shift+left', (await s.js(STATE))['k']))
        await s.key('')                      # ArrowRight
        seq.append(('right', (await s.js(STATE))['k']))
        # Space on a trace long enough to watch (71,900 events at 100/frame)
        await s.open('?perf&bundle=lab1c_dijkstra')
        await s.wait(READY)
        await s.js("document.activeElement && document.activeElement.blur(), 1")
        await s.key(' ')                           # Space: play (restarts from 0)
        await asyncio.sleep(0.5)
        playing = await s.js(STATE)
        seq.append(('space: play', playing['play'], playing['k']))
        await s.key(' ')                           # Space: pause
        await asyncio.sleep(0.3)
        paused = await s.js(STATE)
        await asyncio.sleep(0.5)
        still = await s.js(STATE)
        seq.append(('space: pause', paused['play'], paused['k'], 'k 0.5 s later', still['k']))
        await s.open('?perf&bundle=astar_open')
        await s.wait(READY)
        # scrub: set the range input as a user would (input event)
        await s.js("(() => { const r = document.querySelector('[data-testid=scrub]');"
                   " const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;"
                   " set.call(r, '50'); r.dispatchEvent(new Event('input', {bubbles: true})); return 1; })()")
        await asyncio.sleep(0.2)
        seq.append(('scrub to 50', (await s.js(STATE))['k']))
        # hover a cell
        box = await s.js("(() => { const r = document.querySelector('[data-testid=map-canvas]')"
                         ".getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
        n_cells = 20
        await s.b.cmd('input.performActions', context=s.ctx, actions=[{
            'type': 'pointer', 'id': 'mouse', 'parameters': {'pointerType': 'mouse'},
            'actions': [{'type': 'pointerMove', 'x': int(box[0] + box[2] * 2.5 / n_cells),
                         'y': int(box[1] + box[3] * 15.5 / n_cells)}]}])
        await asyncio.sleep(0.3)
        hover = await s.js("(() => { const p = document.querySelector('[data-testid=hover-panel]');"
                           " return p ? p.innerText : null; })()")
        await s.shot('player_hover')
        return {'sequence': seq, 'hover_panel': hover, 'console_errors': s.errors()}


async def reduced(site, out):
    """prefers-reduced-motion: no autoplay; play advances in discrete jumps."""
    async with Session(site, out, reduced=True) as s:
        await s.open('?perf&bundle=lab1c_dijkstra')
        await s.wait(READY)
        st = await s.js(STATE)
        await asyncio.sleep(1.0)
        still = await s.js(STATE)
        await s.js("document.querySelector('[data-testid=play]').click(), 1")
        ks = []
        for _ in range(12):
            await asyncio.sleep(0.15)
            ks.append((await s.js(STATE))['k'])
        steps = sorted({b - a for a, b in zip(ks, ks[1:]) if b != a})
        return {'matchMedia_reduce': st['reduced'], 'autoplay': still['k'] != st['k'],
                'k_samples_every_150ms': ks, 'distinct_jumps': steps,
                'console_errors': s.errors()}


async def fps(site, out):
    """Play the full-arena native Dijkstra trace; frames drawn per second."""
    async with Session(site, out) as s:
        await s.open('?perf&bundle=arena_native')
        await s.wait(READY, timeout=120)
        st = await s.js(STATE)
        runs = {}
        for speed in (1000, 10000):
            await s.js("(() => { const r = document.querySelector('[data-testid=scrub]');"
                       " const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;"
                       " set.call(r, '0'); r.dispatchEvent(new Event('input', {bubbles: true})); return 1; })()")
            await s.js("(() => { const sel = document.querySelector('select[aria-label=Speed]');"
                       f" const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
                       f" set.call(sel, '{speed}'); sel.dispatchEvent(new Event('change', {{bubbles: true}})); return 1; }})()")
            await asyncio.sleep(0.5)
            await reset_perf(s)
            await s.js("document.querySelector('[data-testid=play]').click(), 1")
            await s.wait(f"(() => {{ const r = document.querySelector('[data-testid=scrub]');"
                         f" return Number(r.value) >= {st['n']}; }})()", timeout=300, every=0.25)
            perf = await s.js("window.__cocoLabPerf")
            ft = perf['frameTimes']
            gaps = [b - a for a, b in zip(ft, ft[1:])]
            dur = (ft[-1] - ft[0]) / 1000.0 if len(ft) > 1 else None
            runs[str(speed)] = {
                'frames': len(ft), 'seconds': round(dur, 3) if dur else None,
                'fps': round((len(ft) - 1) / dur, 2) if dur else None,
                'frame_gap_ms_median': round(statistics.median(gaps), 3) if gaps else None,
                'frame_gap_ms_p95': round(sorted(gaps)[int(0.95 * (len(gaps) - 1))], 3) if gaps else None,
                'frame_gap_ms_max': round(max(gaps), 3) if gaps else None,
                'dropped_frames_gap_over_25ms': sum(1 for g in gaps if g > 25),
                'draw_ms_median': round(statistics.median(perf['frames']), 3),
                'draw_ms_p95': round(sorted(perf['frames'])[int(0.95 * (len(perf['frames']) - 1))], 3),
                'draw_ms_max': round(max(perf['frames']), 3),
            }
        # backward scrub latency: from the end to 0 then to n/2
        t = await s.js("(() => { const r = document.querySelector('[data-testid=scrub]');"
                       " const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;"
                       " const p = window.__cocoLabPerf; p.frames.length = 0;"
                       f" set.call(r, '{st['n'] // 2}'); r.dispatchEvent(new Event('input', {{bubbles: true}}));"
                       " return new Promise(res => requestAnimationFrame(() => requestAnimationFrame("
                       " () => res(p.frames.slice()))));})()")
        await s.shot('fps_arena_native_end')
        return {'events': st['n'], 'runs': runs, 'backward_scrub_draw_ms': t,
                'console_errors': s.errors()}


async def phone(site, out):
    """Replay at phone width: no horizontal scroll, controls hittable."""
    async with Session(site, out, width=390, height=844) as s:
        await s.open('?perf&bundle=lab1c_astar')
        await s.wait(READY)
        r = await s.js("""(() => {
          const hit = (sel) => { const e = document.querySelector(sel); const b = e.getBoundingClientRect();
            e.scrollIntoView({block: 'center'}); const c = e.getBoundingClientRect();
            const x = c.left + c.width / 2, y = c.top + c.height / 2;
            const at = document.elementFromPoint(x, y);
            return { w: Math.round(c.width), h: Math.round(c.height), hit: at === e || e.contains(at) }; };
          window.scrollTo(0, 0);
          return { innerWidth, scrollWidth: document.documentElement.scrollWidth,
            bodyScrollWidth: document.body.scrollWidth,
            play: hit('[data-testid=play]'), scrub: hit('[data-testid=scrub]'),
            picker: hit('[data-testid=picker]'), badge: hit('[data-testid=mode-badge]'),
            canvas: hit('[data-testid=map-canvas]') }; })()""")
        await s.js('window.scrollTo(0, 0), 1')
        await s.shot('phone_390x844_top')
        # a real tap on Play, then check it plays
        await s.js("document.querySelector('[data-testid=play]').scrollIntoView({block: 'center'}), 1")
        box = await s.js("(() => { const b = document.querySelector('[data-testid=play]').getBoundingClientRect();"
                         " return [b.left + b.width / 2, b.top + b.height / 2]; })()")
        await s.b.click(s.ctx, box[0], box[1])
        await asyncio.sleep(0.5)
        after = await s.js(STATE)
        await s.shot('phone_390x844_player')
        r['tap_play'] = {'play_label_after': after['play'], 'k': after['k'], 'n': after['n']}
        r['console_errors'] = s.errors()
        return r


async def weight(site, out):
    """Initial page weight (everything fetched to the first drawn frame)."""
    async with Session(site, out) as s:
        await s.open('?perf')
        await s.wait(READY)
        await asyncio.sleep(1.0)
        res = await s.js("""(() => { const nav = performance.getEntriesByType('navigation')[0];
          const rs = performance.getEntriesByType('resource');
          const row = (e) => ({ name: e.name, transfer: e.transferSize, encoded: e.encodedBodySize,
            decoded: e.decodedBodySize });
          return { nav: row(nav), resources: rs.map(row),
            first_frame_ms: window.__cocoLabPerf.marks['bundle-first-frame'] }; })()""")
        urls = s.requests()
        total_transfer = res['nav']['transfer'] + sum(r['transfer'] for r in res['resources'])
        total_encoded = res['nav']['encoded'] + sum(r['encoded'] for r in res['resources'])
        return {'default_bundle': 'first catalog entry', 'requests': urls,
                'third_party': [u for u in urls if urlparse(u).netloc != urlparse(site).netloc],
                'bytes_transfer': total_transfer, 'bytes_encoded_body': total_encoded,
                'resources': res, 'console_errors': s.errors()}


async def edit(site, out):
    """Pyodide: not requested before an edit; cold then warm edit timings."""
    async with Session(site, out) as s:
        await s.open('?perf&bundle=arena_0_10m')
        await s.wait(READY, timeout=90)
        before = [u for u in s.requests() if 'pyodide' in u or 'jsdelivr' in u]
        await asyncio.sleep(2.0)
        before_idle = [u for u in s.requests() if 'pyodide' in u or 'jsdelivr' in u]
        cat = await catalog(s)
        entry = next(e for e in cat['bundles'] if e['id'] == 'arena_0_10m')
        box = await s.js("(() => { const r = document.querySelector('[data-testid=map-canvas]')"
                         ".getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
        manifest = await s.js(f"fetch('{s.site}generated/{entry['path']}manifest.json').then(r => r.json())")
        w, h = manifest['map']['width'], manifest['map']['height']

        async def click_cell(r, c):
            await s.js("window.scrollTo(0, 0), 1")
            box = await s.js("(() => { const r = document.querySelector('[data-testid=map-canvas]')"
                             ".getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
            x = box[0] + box[2] * (c + 0.5) / w
            y = box[1] + box[3] * (r + 0.5) / h
            await reset_perf(s)
            await s.b.click(s.ctx, x, y)

        results = []
        # cells to toggle: free cells near the middle of the map, off the start/goal
        cells = await s.js(f"""(async () => {{
          const m = {json.dumps(manifest['run'])}; const W = {w}, H = {h};
          return [[Math.floor(H/2), Math.floor(W/2)], [Math.floor(H/2)+3, Math.floor(W/2)+5],
                  [Math.floor(H/2)-4, Math.floor(W/2)-6], [Math.floor(H/2)+1, Math.floor(W/2)-2]];
        }})()""")
        # Lab 1.1: an edit is a brush stroke; a click with the 1 x 1 brush
        # paints one cell, the same change 1D's click-to-toggle made on a
        # free cell. Choosing the tool starts no Python (checked below).
        await click_testid(s, 'tool-paint')
        for i, (r, c) in enumerate(cells):
            t0 = time.time()
            await click_cell(r, c)
            await s.wait("(() => { const e = document.querySelector('[data-testid=edit-status]');"
                         " return e && !e.classList.contains('busy') ? e.className : null; })()",
                         timeout=300, every=0.05)
            await s.wait("window.__cocoLabPerf.marks['edit-first-frame'] ||"
                         " document.querySelector('[data-testid=edit-status].error')", timeout=30, every=0.05)
            perf = await s.js("window.__cocoLabPerf.marks")
            st = await s.js("(() => ({ text: document.querySelector('[data-testid=edit-status]').innerText,"
                            " cls: document.querySelector('[data-testid=edit-status]').className,"
                            " badge: document.querySelector('[data-testid=mode-badge]').textContent }))()")
            ms = (perf['edit-first-frame'] - perf['edit-click']) if 'edit-first-frame' in perf else None
            results.append({'edit': i + 1, 'cell': [r, c], 'wall_s': round(time.time() - t0, 3),
                            'click_to_first_frame_ms': round(ms, 1) if ms else None,
                            'status': st['text'], 'class': st['cls'], 'badge': st['badge']})
            if i == 0:
                await s.shot('edit_first')
        await s.shot('edit_last')
        pyodide_reqs = [u for u in s.requests() if urlparse(u).netloc != urlparse(site).netloc]
        return {'pyodide_requests_before_edit': before + before_idle,
                'third_party_after_edits': sorted(set(pyodide_reqs)),
                'edits': results, 'console_errors': s.errors()}


async def lab(site, out):
    """
    Lab 1.1 Part A on the teaching grid, by real pointer and keys.

    Settings (the coco_lab badge and bound as the page shows them, then a
    run), a painted stroke, a stroke over the start (refused before any
    Python), a four-way race, and the map ladder with the footprint sweep.
    """
    async with Session(site, out) as s:
        await s.open('?perf&bundle=astar_open')
        await s.wait(READY, timeout=90)
        rep = {'python_before_any_change': [u for u in s.requests() if 'pyodide' in u]}
        rep['badge_8_octile'] = await s.js(TEXT.format('heuristic-badge'))
        await click_testid(s, 'set-conn-4')
        rep['badge_4_octile'] = await s.js(TEXT.format('heuristic-badge'))
        await click_testid(s, 'set-conn-8')
        await focus_testid(s, 'set-heuristic')
        await s.key('')  # Home: 'zero'
        await s.key('')  # ArrowDown: 'manhattan'
        rep['badge_8_manhattan'] = await s.js(TEXT.format('heuristic-badge'))
        rep['bound_astar_manhattan'] = await s.js(TEXT.format('bound'))
        await s.key('')  # End: 'octile'
        await focus_testid(s, 'set-algorithm')
        await s.key('')  # End: weighted_astar
        # the slider is enabled only once React has re-rendered for weighted A*
        await s.wait("!document.querySelector('[data-testid=set-weight]').disabled", timeout=5)
        await focus_testid(s, 'set-weight')
        for _ in range(5):
            await s.key('')  # ArrowRight: w 1.00 -> 2.25
        rep['bound_wastar_2_25'] = await s.js(TEXT.format('bound'))
        await click_testid(s, 'set-tie-fifo')
        await click_testid(s, 'predict-cost-more')  # predict-then-reveal (Part B)
        await s.shot('lab_settings')
        t0 = time.time()
        await click_testid(s, 'run-settings')
        await s.wait(STATUS_SETTLED, timeout=300, every=0.1)
        rep['settings_run'] = {'status': await s.js(TEXT.format('edit-status')),
                               'badge': await s.js(TEXT.format('mode-badge')),
                               'reveal': await s.js(TEXT.format('reveal')),
                               'wall_s': round(time.time() - t0, 2)}
        await s.shot('lab_settings_run')

        await click_testid(s, 'tool-paint')
        await focus_testid(s, 'brush')
        await s.key('')  # brush 3 x 3
        await drag_cells(s, [(10, 4), (10, 8), (10, 12)], 20, 20)
        await s.wait(STATUS_SETTLED, timeout=120, every=0.1)
        rep['paint'] = await s.js(TEXT.format('edit-status'))
        await s.shot('lab_paint')
        await drag_cells(s, [(15, 2)], 20, 20)  # the start cell
        await asyncio.sleep(0.3)
        rep['paint_over_start'] = {
            'status': await s.js(TEXT.format('edit-status')),
            'class': await s.js(STATUS_SETTLED)}

        for a in ('bfs', 'greedy'):
            await click_testid(s, f'race-{a}')
        await click_testid(s, 'predict-fewest-astar')
        await click_testid(s, 'race-start')
        await s.wait("document.querySelector('[data-testid=race-table]')", timeout=120)
        rep['race'] = {
            'panes': await s.js("document.querySelectorAll('[data-testid=race-pane]').length"),
            'table': await s.js(TEXT.format('race-table')),
            'reveal': await s.js(TEXT.format('reveal')),
            'status': await s.js(TEXT.format('edit-status'))}
        await s.js("(document.querySelector('[data-testid=race]').scrollIntoView({block: 'start'}), 1)")
        await s.shot('lab_race')
        await click_testid(s, 'race-close')

        rungs = {}
        for n in (2, 3):
            await reset_perf(s)
            await click_testid(s, f'rung-{n}')
            await s.wait("window.__cocoLabPerf.marks['bundle-first-frame']", timeout=60)
            await asyncio.sleep(0.3)
            rungs[n] = {'picker': await s.js(
                "document.querySelector('[data-testid=picker]').selectedOptions[0].textContent"),
                'sweep_note': await s.js(TEXT.format('sweep-note'))}
            await s.shot(f'lab_rung{n}')
        rep['ladder'] = rungs
        rep['third_party'] = sorted({u for u in s.requests()
                                     if urlparse(u).netloc != urlparse(site).netloc})
        rep['console_errors'] = s.errors()
        return rep


VERDICT = ("(() => { const e = document.querySelector('[data-testid=share-verdict]');"
           " return e ? e.innerText : null; })()")


async def share(site, out):
    """
    Share links in a real browser: make one from a painted, re-set view;
    open it in a FRESH page; coco_lab reruns it and the page compares the
    trace digest. Then the two committed CI vectors (test/golden), opened
    as links.
    """
    rep = {}
    async with Session(site, out) as s:
        await s.open('?perf&bundle=astar_open')
        await s.wait(READY, timeout=90)
        await click_testid(s, 'tool-paint')
        await drag_cells(s, [(8, 6), (8, 10), (8, 14)], 20, 20)
        await s.wait(STATUS_SETTLED, timeout=300, every=0.1)
        await click_testid(s, 'set-conn-4')
        await click_testid(s, 'run-settings')
        await s.wait(STATUS_SETTLED, timeout=120, every=0.1)
        await click_testid(s, 'share-make')
        await s.wait("document.querySelector('[data-testid=share-link]')", timeout=10)
        link = await s.js("document.querySelector('[data-testid=share-link]').value")
        made = {'link': link, 'digest_on_page': None}
        rep['made'] = made
    query = link[link.index('?'):]
    snap_path = os.path.join(HERE, '..', '..', 'test', '__snapshots__', 'share.test.ts.snap')
    with open(snap_path) as f:
        vectors = re.findall(r'"(\?v=1&[^"]+)"', f.read())
    rep['opened'] = []
    for q in [query] + vectors:
        async with Session(site, out) as s:
            t0 = time.time()
            await s.open(q)
            await s.wait(VERDICT, timeout=300, every=0.2)
            rep['opened'].append({'query': q, 'verdict': await s.js(VERDICT),
                                  'wall_s': round(time.time() - t0, 1), 'console_errors': s.errors()})
            if q is query:
                await s.shot('share_opened')
    return rep


async def replay(site, out):
    """A recorded run: provenance, the tracking-error plot, a hover readout, the table view."""
    async with Session(site, out) as s:
        await s.open('?perf&bundle=lab1c_astar')
        await s.wait(READY, timeout=90)
        await s.wait("document.querySelector('[data-testid=tracking-plot]')", timeout=30)
        b = await box_of(s, 'tracking-plot')
        await s.b.cmd('input.performActions', context=s.ctx, actions=[{
            'type': 'pointer', 'id': 'mouse', 'parameters': {'pointerType': 'mouse'},
            'actions': [{'type': 'pointerMove', 'x': int(b[0] + b[2] * 0.4), 'y': int(b[1] + b[3] / 2)}]}])
        await s.wait("document.querySelector('[data-testid=tracking-tip]')", timeout=5)
        rep = {'provenance': await s.js(TEXT.format('run-provenance')),
               'tip': await s.js(TEXT.format('tracking-tip')),
               'table': await s.js(TEXT.format('tracking-table')),
               'badge': await s.js(TEXT.format('mode-badge')),
               'points': await s.js("document.querySelector('[data-testid=tracking-plot] .series')"
                                    ".getAttribute('d').split(/[ML]/).length - 1"),
               'console_errors': s.errors()}
        await s.js("(document.querySelector('[data-testid=tracking]').scrollIntoView({block: 'start'}), 1)")
        await s.shot('replay_tracking')
        return rep


async def exhibit(site, out):
    """The exhibit: (a) run live, (b) and (c) read from the evidence."""
    async with Session(site, out) as s:
        await s.open('?perf&bundle=astar_open')
        await s.wait(READY, timeout=90)
        await click_testid(s, 'view-exhibit')
        await s.wait("document.querySelector('[data-testid=exhibit-run]')", timeout=30)
        await click_testid(s, 'exhibit-run')
        await s.wait("document.querySelector('[data-testid=exhibit-a-verdict]')", timeout=300, every=0.2)
        rep = {'a': await s.js(TEXT.format('exhibit-a-verdict')),
               'b_table': await s.js(TEXT.format('exhibit-b-table')),
               'c_label': await s.js(TEXT.format('exhibit-c-label'))}
        await s.js("(document.querySelector('[data-testid=exhibit]').scrollIntoView({block: 'start'}), 1)")
        await s.shot('exhibit_top')
        await s.js("(document.querySelector('[data-testid=exhibit-b]').scrollIntoView({block: 'start'}), 1)")
        await s.shot('exhibit_b')
        await reset_perf(s)
        await click_testid(s, 'exhibit-c-open')
        await s.wait("window.__cocoLabPerf.marks['bundle-first-frame']", timeout=60)
        rep['c_opens'] = await s.js(
            "document.querySelector('[data-testid=picker]').selectedOptions[0].textContent")
        rep['console_errors'] = s.errors()
        return rep


SCENARIOS = {'smoke': smoke, 'player': player, 'reduced': reduced, 'fps': fps,
             'phone': phone, 'weight': weight, 'edit': edit, 'lab': lab,
             'share': share, 'replay': replay, 'exhibit': exhibit}


async def main(argv):
    site, out = argv[0], argv[1]
    if not site.endswith('/'):
        site += '/'
    names = argv[2:] or list(SCENARIOS)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, 'report.json')
    report = json.load(open(path)) if os.path.exists(path) else {}
    report['_meta'] = {'site': site, 'firefox': subprocess.run(
        ['firefox', '--version'], capture_output=True, text=True).stdout.strip(),
        'headless': True, 'loadavg': open('/proc/loadavg').read().split()[:3],
        'when_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    for name in names:
        print(f'-- {name}', flush=True)
        report[name] = await SCENARIOS[name](site, out)
        report[name]['_loadavg'] = open('/proc/loadavg').read().split()[:3]
        with open(path, 'w') as f:
            json.dump(report, f, indent=1, sort_keys=True)
    print(json.dumps({k: report[k] for k in names}, indent=1)[:6000])


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1:]))
