"""coco.v1 client for the safety-fix validation. Logs everything (wall clock).

  probe.py OUT stop STAGE COLOUR DELAY   mission; page-style STOP DELAY s into STAGE; watch 15 s
  probe.py OUT nav                        no mission; set_mode auto; 5+ goals on free floor
  probe.py OUT fetch COLOUR               one full mission, to COMPLETE or ABORT
"""
import asyncio
import base64
import json
import math
import sys
import time

import tornado.websocket

URL = 'ws://127.0.0.1:8080/ws'
OUT, SCEN, ARGS = sys.argv[1], sys.argv[2], sys.argv[3:]
log = open(OUT, 'a', buffering=1)
st = {'tele': None, 'welcome': None, 'map': None, 'replies': {}}
fid = [0]


def w(kind, **kw):
    log.write(json.dumps({'t': time.time(), 'kind': kind, **kw}) + '\n')


def summary(f):
    r, m, n, p = f['robot'], f['mission'] or {}, f['nav'], f['platform']
    a = p.get('arbiter') or {}
    return {'seq': f['seq'], 'pose': r.get('pose'), 'frame': r.get('frame'),
            'localised': r.get('localised'), 'nav_online': n.get('online'),
            'path_n': len(n.get('path') or []),
            'arb_mode': a.get('mode'), 'arb_active': a.get('active'),
            'm_state': m.get('state'), 'm_mode': m.get('mode'),
            'm_online': m.get('online'), 'm_active': m.get('active'),
            'm_reason': m.get('reason'), 'm_result': m.get('result'),
            'pilot': p.get('pilot'), 'stop': p.get('stop'),
            'health': p.get('health')}


async def reader(ws):
    while True:
        msg = await ws.read_message()
        if msg is None:
            w('closed')
            return
        if isinstance(msg, bytes):
            continue
        f = json.loads(msg)
        if f['type'] == 'telemetry':
            s = summary(f)
            st['tele'] = s
            w('tele', **s)
        elif f['type'] == 'map':
            st['map'] = f
            w('map', width=f['width'], height=f['height'])
        elif f['type'] == 'welcome':
            st['welcome'] = f
            w('welcome', world=f.get('world'))
        else:
            if f.get('id') is not None:
                st['replies'][f['id']] = f
            w('rx', frame=f)


async def send(ws, frame):
    fid[0] += 1
    frame = dict(frame, id=fid[0])
    w('tx', frame=frame)
    await ws.write_message(json.dumps(frame))
    return fid[0]


async def wait_for(pred, timeout, label):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = st['tele']
        if s and pred(s):
            w('cond', label=label, ok=True, after=time.time() - t0)
            return True
        await asyncio.sleep(0.05)
    w('cond', label=label, ok=False, after=timeout)
    return False


async def page_stop(ws):
    """Exactly what the page's STOP button sends."""
    await send(ws, {'type': 'stop'})
    for _ in range(3):
        await asyncio.sleep(0.1)
        await send(ws, {'type': 'drive', 'linear': 0.0, 'angular': 0.0})
    await send(ws, {'type': 'set_mode', 'mode': 'stop'})


def free(x, y, clearance=0.45):
    """Map cells within `clearance` of (x, y) are all known-free."""
    m = st['map']
    cells = base64.b64decode(m['data'])
    res, ox, oy = m['resolution'], m['origin']['x'], m['origin']['y']
    r = int(clearance / res)
    cx, cy = int((x - ox) / res), int((y - oy) / res)
    for j in range(cy - r, cy + r + 1):
        for i in range(cx - r, cx + r + 1):
            if not (0 <= i < m['width'] and 0 <= j < m['height']):
                return False
            v = cells[j * m['width'] + i]
            if v != 0:
                return False
    return True


async def scen_stop(ws, stage, colour, delay):
    await send(ws, {'type': 'select_target', 'colour': colour})
    await asyncio.sleep(1)
    await send(ws, {'type': 'mission', 'action': 'start'})
    ok = await wait_for(lambda s: s['m_state'] == stage, 600, 'stage_' + stage)
    if not ok:
        return
    source = {'NAVIGATE_TO_RAMP': 'nav', 'CLIMB': 'rl', 'DESCEND': 'rl',
              'APPROACH_TARGET': 'approach'}.get(stage)
    if source:
        # Mid-stage means DRIVING: the stage's own source on the wheels.
        await wait_for(lambda s: s['arb_active'] == source, 120,
                       'driving_' + source)
    await asyncio.sleep(delay)
    w('phase', name='STOP', state=st['tele']['m_state'])
    await page_stop(ws)
    await asyncio.sleep(15)
    w('phase', name='end')


async def scen_nav(ws):
    await wait_for(lambda s: st['map'] is not None, 30, 'map')
    candidates = [(1.0, 0.0), (1.5, -1.2), (0.5, 1.2), (2.0, 0.5),
                  (0.0, -1.5), (1.5, 1.5), (-0.5, 0.8), (2.5, -0.5),
                  (0.0, 0.0)]
    goals = [g for g in candidates if free(*g)]
    w('goals', goals=goals, rejected=[g for g in candidates if g not in goals])
    await send(ws, {'type': 'set_mode', 'mode': 'auto'})
    await asyncio.sleep(1)
    for x, y in goals:
        w('phase', name='goal', x=x, y=y)
        await send(ws, {'type': 'nav_goal', 'x': x, 'y': y})

        def arrived(s):
            p = s['pose'] or {}
            return math.hypot(p.get('x', 99) - x, p.get('y', 99) - y) < 0.3
        ok = await wait_for(arrived, 90, f'arrive_{x}_{y}')
        await asyncio.sleep(3 if ok else 1)
    w('phase', name='end')


async def scen_fetch(ws, colour):
    await send(ws, {'type': 'select_target', 'colour': colour})
    await asyncio.sleep(1)
    await send(ws, {'type': 'mission', 'action': 'start'})
    await wait_for(lambda s: s['m_state'] in ('COMPLETE', 'ABORT'), 1500,
                   'terminal')
    await asyncio.sleep(3)
    w('phase', name='end', state=st['tele']['m_state'],
      result=st['tele']['m_result'], reason=st['tele']['m_reason'])


async def main():
    t0 = time.time()
    ws = await tornado.websocket.websocket_connect(URL)
    task = asyncio.ensure_future(reader(ws))
    await send(ws, {'type': 'hello', 'client': 'live-validation',
                    'binary': False})
    w('phase', name='wait')
    await wait_for(lambda s: s['localised'], 300, 'localised')
    w('localised_after', s=time.time() - t0)
    await wait_for(lambda s: s['nav_online'] and s['m_online'], 300, 'ready')
    await asyncio.sleep(2)
    if SCEN == 'stop':
        await scen_stop(ws, ARGS[0], ARGS[1], float(ARGS[2]))
    elif SCEN == 'nav':
        await scen_nav(ws)
    elif SCEN == 'fetch':
        await scen_fetch(ws, ARGS[0])
    ws.close()
    await asyncio.sleep(0.5)
    task.cancel()


asyncio.run(main())
