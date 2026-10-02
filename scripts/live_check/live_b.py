"""
Drive the Live tab in headless Firefox (WebDriver BiDi) and log what it did.

    live_b.py OUT URL teleop_nav            teleop latency presses, STOP, Nav2 goals
    live_b.py OUT URL fetch COLOUR [preempt] one fetch from the page; optional preemption

Every action is a real key press or pointer click on the shipped page. The
page's own send log (wall-clock ms, stamped as each frame leaves the page)
and its telemetry are dumped to OUT/page.json for analyse_b.py to join with
the ROS recorder.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'browser_check'))
from bidi import Bidi, launch  # noqa: E402

OUT, URL, SCEN, ARGS = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
PORT = 9226
log = open(os.path.join(OUT, 'actions.jsonl'), 'a', buffering=1)

#: Map-frame goals on free floor (each had a 0.45 m free neighbourhood on
#: this map in the safety-fix runs; docs/live/SAFETY_FIXES.md).
GOALS = [(1.0, 0.0), (0.5, 1.2), (2.0, 0.5), (0.0, -1.5), (-0.5, 0.8),
         (2.5, -0.5), (0.0, 0.0)]


def w(kind, **kw):
    log.write(json.dumps({'t': time.time(), 'kind': kind, **kw}) + '\n')


async def tele(b, ctx):
    return await b.eval(ctx, 'window.__cocoLiveTele || null')


async def wait_tele(b, ctx, js_pred, timeout, label):
    t0 = time.time()
    while time.time() - t0 < timeout:
        ok = await b.eval(ctx, f'(() => {{ const t = window.__cocoLiveTele; '
                               f'return !!t && ({js_pred}); }})()')
        if ok:
            w('cond', label=label, ok=True, after=time.time() - t0)
            return True
        await asyncio.sleep(0.2)
    w('cond', label=label, ok=False, after=timeout)
    return False


async def click_testid(b, ctx, tid):
    box = await b.eval(ctx, (
        f'(() => {{ const e = document.querySelector(\'[data-testid="{tid}"]\');'
        ' if (!e) return null; e.scrollIntoView({block: "center"});'
        ' const r = e.getBoundingClientRect();'
        ' return [r.left + r.width / 2, r.top + r.height / 2]; })()'))
    if box is None:
        raise RuntimeError(f'no element {tid}')
    w('click', target=tid, t_page=await now_ms(b, ctx))
    await b.click(ctx, box[0], box[1])


async def now_ms(b, ctx):
    return await b.eval(ctx, 'performance.timeOrigin + performance.now()')


async def dom(b, ctx):
    return await b.eval(ctx, '''(() => {
      const q = (id) => document.querySelector(`[data-testid="${id}"]`);
      const tx = (id) => (q(id) ? q(id).textContent : null);
      return {badge: tx('mode-badge'), conn: tx('live-conn'), rate: tx('live-rate'),
              fallback: tx('live-fallback'), latched: tx('live-latched'),
              override: tx('live-override'), mode: tx('live-mode'),
              source: tx('live-source'), holder: tx('live-holder'),
              lane: tx('live-lane-told'), mission: tx('live-mission'),
              goal: tx('live-goal'), localised: tx('live-localised'),
              timeline: [...document.querySelectorAll('[data-testid="live-timeline"] li')].map(e => e.textContent)};
    })()''')


async def press(b, ctx, key, hold_ms):
    await b.keys(ctx, [{'type': 'keyDown', 'value': key},
                       {'type': 'pause', 'duration': hold_ms},
                       {'type': 'keyUp', 'value': key}])


async def teleop_nav(b, ctx):
    await click_testid(b, ctx, 'live-panel-teleop')
    await asyncio.sleep(1.0)
    w('phase', name='presses')
    for i in range(40):
        await press(b, ctx, 'w' if i % 2 == 0 else 's', 400)
        await asyncio.sleep(1.1)
    w('phase', name='stop_while_held')
    await b.keys(ctx, [{'type': 'keyDown', 'value': 'w'}])
    await asyncio.sleep(0.8)
    await click_testid(b, ctx, 'live-stop')
    await asyncio.sleep(0.3)
    await b.keys(ctx, [{'type': 'keyUp', 'value': 'w'}])
    await asyncio.sleep(3.0)
    w('dom_after_stop', dom=await dom(b, ctx))
    w('phase', name='nav2')
    await click_testid(b, ctx, 'live-panel-nav2')
    await asyncio.sleep(1.0)
    for x, y in GOALS:
        pt = await b.eval(ctx, f'window.__cocoLiveToScreen({x}, {y})')
        w('goal', x=x, y=y, screen=pt, t_page=await now_ms(b, ctx))
        await b.click(ctx, pt[0], pt[1])
        ok = await wait_tele(
            b, ctx, f"t.nav.goal && Math.abs(t.nav.goal.x - {x}) < 0.05 && "
                    f"Math.abs(t.nav.goal.y - {y}) < 0.05 && "
                    "['succeeded','aborted','canceled'].includes(t.nav.goal.status)",
            120, f'goal_{x}_{y}')
        t = await tele(b, ctx)
        w('goal_done', x=x, y=y, ok=ok, status=(t['nav'].get('goal') or {}).get('status'),
          pose=t['robot'].get('pose'), truth=t['robot'].get('truth'))
        await asyncio.sleep(1.5)


async def fetch(b, ctx, colour, preempt):
    await click_testid(b, ctx, 'live-panel-auto')
    await asyncio.sleep(0.5)
    await click_testid(b, ctx, f'live-colour-{colour}')
    await asyncio.sleep(1.0)
    await click_testid(b, ctx, 'live-start')
    if preempt:
        await wait_tele(b, ctx, "t.mission && t.mission.state === 'NAVIGATE_TO_RAMP' "
                                "&& t.nav.active_source === 'nav'", 180, 'nav_leg')
        await asyncio.sleep(2.0)
        w('phase', name='preempt')
        await b.keys(ctx, [{'type': 'keyDown', 'value': 'a'}])
        seen = None
        t0 = time.time()
        while time.time() - t0 < 2.5:
            d = await dom(b, ctx)
            if d['override'] and seen is None:
                seen = time.time() - t0
            await asyncio.sleep(0.1)
        await b.keys(ctx, [{'type': 'keyUp', 'value': 'a'}])
        w('preempt', override_banner_after_s=seen)
        await asyncio.sleep(3.0)
        w('dom_after_release', dom=await dom(b, ctx))
    await wait_tele(b, ctx, "t.mission && ['COMPLETE','ABORT'].includes(t.mission.state)",
                    1500, 'terminal')
    await asyncio.sleep(2.0)


async def main():
    proc = launch(port=PORT, width=1400, height=1000)
    try:
        b = await Bidi.connect(port=PORT)
        await b.cmd('session.new', capabilities={})
        tree = await b.cmd('browsingContext.getTree')
        ctx = tree['contexts'][0]['context']
        await b.cmd('browsingContext.navigate', context=ctx, url=URL, wait='complete')
        ok = await wait_tele(b, ctx, 't.robot.online && t.nav.online && t.mission && t.mission.online',
                             300, 'ready')
        await wait_tele(b, ctx, 't.robot.localised', 60, 'localised')
        w('dom_start', dom=await dom(b, ctx))
        await b.shot(ctx, os.path.join(OUT, 'start.png'))
        if ok and SCEN == 'teleop_nav':
            await teleop_nav(b, ctx)
        elif ok and SCEN == 'fetch':
            await fetch(b, ctx, ARGS[0], 'preempt' in ARGS[1:])
        await b.shot(ctx, os.path.join(OUT, 'end.png'))
        w('dom_end', dom=await dom(b, ctx))
        page = await b.eval(ctx, '''(() => ({
          log: window.__cocoLive ? window.__cocoLive.log : [],
          telemetryRx: window.__cocoLive ? window.__cocoLive.telemetryRx : [],
          dateNow: Date.now(), perfNow: performance.timeOrigin + performance.now()}))()''')
        json.dump(page, open(os.path.join(OUT, 'page.json'), 'w'))
        w('done')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            proc.kill()


asyncio.run(main())
