"""Drive the coco.v1 socket through the Part A live questions; log everything.

Phases (all wall-clock stamped in the JSONL):
  wait   localised + nav online + mission online
  M      select_target blue, mission start, wait for the nav leg to be driving
  P      teleop preemption: drive angular 0.8 at 10 Hz for 3 s, then release
  S      the page's STOP during the mission: stop, 3 zero drives, set_mode stop
  A      mission abort
  N      Nav2 mode with the executive idle: set_mode auto, nav_goal
  T      plain teleop: set_mode teleop, drive 0.15 m/s for 2 s, stop
"""
import asyncio
import json
import sys
import time

import tornado.websocket

URL = 'ws://127.0.0.1:8080/ws'
log = open(sys.argv[1], 'a', buffering=1)
state = {'tele': None, 'n_tele': 0}
fid = [0]


def w(kind, **kw):
    log.write(json.dumps({'t': time.time(), 'kind': kind, **kw}) + '\n')


def summary(f):
    r, m, n, p = f['robot'], f['mission'] or {}, f['nav'], f['platform']
    a = p.get('arbiter') or {}
    return {'seq': f['seq'], 'ts': f['t'], 'pose': r.get('pose'),
            'localised': r.get('localised'), 'nav_online': n.get('online'),
            'path_n': len(n.get('path') or []),
            'active_source': n.get('active_source'),
            'arb_mode': a.get('mode'), 'arb_active': a.get('active'),
            'm_state': m.get('state'), 'm_mode': m.get('mode'),
            'm_online': m.get('online'), 'm_active': m.get('active'),
            'm_reason': m.get('reason'), 'pilot': p.get('pilot'),
            'health': p.get('health')}


async def reader(ws):
    while True:
        msg = await ws.read_message()
        if msg is None:
            w('closed')
            return
        if isinstance(msg, bytes):
            w('binary', n=len(msg))
            continue
        f = json.loads(msg)
        if f['type'] == 'telemetry':
            s = summary(f)
            state['tele'] = s
            state['n_tele'] += 1
            w('tele', **s)
        elif f['type'] == 'map':
            w('map', width=f['width'], height=f['height'])
        elif f['type'] == 'welcome':
            w('welcome', session=f['session'].get('state'),
              commands=f['commands'], limits=f['limits'])
        else:
            w('rx', frame=f)


async def send(ws, frame):
    fid[0] += 1
    frame = dict(frame, id=fid[0])
    w('tx', frame=frame)
    await ws.write_message(json.dumps(frame))


async def wait_for(pred, timeout, label):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = state['tele']
        if s and pred(s):
            w('cond', label=label, ok=True, after=time.time() - t0)
            return True
        await asyncio.sleep(0.1)
    w('cond', label=label, ok=False, after=timeout)
    return False


async def drive_for(ws, lin, ang, seconds):
    end = time.time() + seconds
    while time.time() < end:
        await send(ws, {'type': 'drive', 'linear': lin, 'angular': ang})
        await asyncio.sleep(0.1)


async def main():
    ws = await tornado.websocket.websocket_connect(URL)
    task = asyncio.ensure_future(reader(ws))
    await send(ws, {'type': 'hello', 'client': 'part-a-probe',
                    'binary': False})
    w('phase', name='wait')
    await wait_for(lambda s: s['localised'] and s['nav_online']
                   and s['m_online'], 400, 'ready')
    await asyncio.sleep(3)

    w('phase', name='M')
    await send(ws, {'type': 'select_target', 'colour': 'blue'})
    await asyncio.sleep(1)
    await send(ws, {'type': 'mission', 'action': 'start'})
    ok = await wait_for(lambda s: s['m_mode'] == 'nav'
                        and s['arb_active'] == 'nav', 120, 'nav_leg_driving')
    await asyncio.sleep(2)

    w('phase', name='P', mission_driving=ok)
    await drive_for(ws, 0.0, 0.8, 3.0)
    w('phase', name='P_release')
    await asyncio.sleep(5)

    w('phase', name='S')
    await send(ws, {'type': 'stop'})
    for _ in range(3):
        await asyncio.sleep(0.1)
        await send(ws, {'type': 'drive', 'linear': 0.0, 'angular': 0.0})
    await send(ws, {'type': 'set_mode', 'mode': 'stop'})
    await asyncio.sleep(8)

    w('phase', name='A')
    await send(ws, {'type': 'mission', 'action': 'abort'})
    await asyncio.sleep(5)

    w('phase', name='N')
    await send(ws, {'type': 'set_mode', 'mode': 'auto'})
    await asyncio.sleep(1)
    await send(ws, {'type': 'nav_goal', 'x': 1.0, 'y': 0.0})
    await asyncio.sleep(25)

    w('phase', name='T')
    await send(ws, {'type': 'set_mode', 'mode': 'teleop'})
    await asyncio.sleep(0.5)
    await drive_for(ws, 0.15, 0.0, 2.0)
    await send(ws, {'type': 'stop'})
    await asyncio.sleep(3)
    w('phase', name='end', telemetry_frames=state['n_tele'])
    ws.close()
    await asyncio.sleep(0.5)
    task.cancel()


asyncio.run(main())
