"""Phase 2 Part C: a full fetch in the REMOTE session configuration.

  probe_remote_fetch.py OUT URL ORIGIN COLOUR

What C2 (probe_session.py) did not drive live, on the real coco.v1 path,
with the policy's real defaults (idle 60 s, cap 20 min):

  1. rate limiting: a driver burst of `drive`, and a flooding spectator
     closed after 100 refusals in a row (4429);
  2. the Nav2 lease: `lease: autonomy` while the browser's goal runs;
  3. a full autonomous fetch started by the driver, which then sends
     NOTHING: the driver must keep control past idle_s because autonomy
     holds the lease, with `last_input_s` growing (no faked activity);
  4. a spectator's STOP and abort mid-mission: refused, mission unaffected;
  5. after the mission, the lease returns to the driver and the idle
     release fires about idle_s later, with STOP latched;
  6. reclaim, then the host's kill switch closes the socket.

The control code comes from the HOST (scripts/live_session.sh code).
Every frame sent and received is logged, wall-clock stamped, to OUT.
URL may be a wss:// tunnel URL: nothing here assumes loopback.
"""
import asyncio
import json
import pathlib
import re
import ssl
import subprocess
import sys
import time

from tornado.httpclient import HTTPRequest
import tornado.websocket

OUT, URL, ORIGIN, COLOUR = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
HOST = str(pathlib.Path(__file__).resolve().parents[5] / 'scripts' / 'live_session.sh')
log = open(OUT, 'a', buffering=1)
RESULTS = []


def w(kind, **kw):
    log.write(json.dumps({'t': time.time(), 'kind': kind, **kw}) + '\n')


def host(action):
    out = subprocess.run(['bash', HOST, action], capture_output=True, text=True,
                         timeout=60).stdout.strip()
    w('host', action=action, out=out)
    return out


def code_of(text):
    m = re.search(r'control code ([A-Z0-9]{8})', text)
    return m.group(1) if m else None


def check(name, got, want):
    ok = got == want if not callable(want) else bool(want(got))
    RESULTS.append(ok)
    w('check', name=name, got=got, want=str(want), ok=ok)
    print(f'{"PASS" if ok else "FAIL"} {name}: got {got!r}', flush=True)


class Client:
    def __init__(self, name):
        self.name, self.n, self.replies = name, 0, {}
        self.tele, self.closed, self.ctl = None, None, {}

    async def open(self):
        req = HTTPRequest(URL, headers={'Origin': ORIGIN},
                          ssl_options=ssl.create_default_context())
        self.ws = await tornado.websocket.websocket_connect(req)
        self.task = asyncio.ensure_future(self.read())
        await self.send({'type': 'hello', 'client': self.name, 'binary': False})
        return self

    async def read(self):
        while True:
            msg = await self.ws.read_message()
            if msg is None:
                self.closed = (time.time(), self.ws.close_code, self.ws.close_reason)
                w('closed', who=self.name, code=self.ws.close_code,
                  reason=self.ws.close_reason)
                return
            if isinstance(msg, bytes):
                continue
            f = json.loads(msg)
            if f['type'] == 'telemetry':
                self.tele = f
                self.ctl = f['platform'].get('control') or {}
                m = f.get('mission') or {}
                w('tele', who=self.name, seq=f.get('seq'), control=self.ctl,
                  latched=(f['platform'].get('stop') or {}).get('latched'),
                  vel=f['robot'].get('velocity'), m_state=m.get('state'),
                  m_result=m.get('result'), m_reason=m.get('reason'),
                  goal=f['nav'].get('goal'), localised=f['robot'].get('localised'))
            elif f['type'] in ('ack', 'error'):
                self.replies[f.get('id')] = f
                w('rx', who=self.name, frame=f)

    async def send(self, frame):
        self.n += 1
        frame = dict(frame, id=f'{self.name}{self.n}')
        w('tx', who=self.name, frame=frame)
        await self.ws.write_message(json.dumps(frame))
        return frame['id']

    async def ask(self, frame, timeout=5.0):
        fid = await self.send(frame)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if fid in self.replies:
                return self.replies[fid].get('code') or 'ack'
            await asyncio.sleep(0.02)
        return 'timeout'

    def state(self):
        return ((self.tele or {}).get('mission') or {}).get('state')


async def until(pred, timeout, label):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if pred():
                w('cond', label=label, ok=True, after=time.time() - t0)
                return time.time() - t0
        except (KeyError, TypeError, AttributeError):
            pass
        await asyncio.sleep(0.05)
    w('cond', label=label, ok=False, after=timeout)
    return None


async def main():
    code = code_of(host('code'))
    check('host issued a code', bool(code), True)
    a = await Client('A').open()
    b = await Client('B').open()
    await until(lambda: a.tele['robot'].get('localised'), 300, 'localised')
    await until(lambda: a.tele['nav'].get('online')
                and (a.tele.get('mission') or {}).get('online'), 300, 'ready')
    await asyncio.sleep(2)

    w('phase', name='claim')
    # With nobody driving, so the code itself is what is judged (with a
    # driver present every claim is driver_present, whatever its code).
    check('invalid code, no driver', await b.ask({'type': 'claim', 'code': 'WRONG234'}), 'bad_code')
    check('driver claim', await a.ask({'type': 'claim', 'code': code}), 'ack')
    check('second claim, right code', await b.ask({'type': 'claim', 'code': code}), 'driver_present')
    check('second claim, wrong code', await b.ask({'type': 'claim', 'code': 'WRONG234'}), 'driver_present')
    check('lease after claim', a.ctl.get('lease') if await until(
        lambda: a.ctl.get('driver'), 3, 'ctl') is not None else None, 'driver')

    w('phase', name='rate_limit_driver')
    ids = [await a.send({'type': 'drive', 'linear': 0.0, 'angular': 0.0}) for _ in range(40)]
    await until(lambda: all(i in a.replies for i in ids), 5, 'burst_replies')
    codes = [a.replies.get(i, {}).get('code') or a.replies.get(i, {}).get('type') for i in ids]
    w('burst', codes=codes)
    check('driver drive burst of 40: some rate_limited', codes.count('rate_limited'), lambda n: n > 0)
    check('driver drive burst of 40: some admitted', codes.count('ack'), lambda n: n > 0)
    check('driver STOP right after the burst is not rate limited',
          await a.ask({'type': 'stop'}), 'ack')

    w('phase', name='flood')
    r = await Client('R').open()
    await asyncio.sleep(1)
    # A spectator flooding a command: every frame is refused (spectator, or
    # rate_limited once its frame bucket is empty), so 100 in a row close it.
    for _ in range(300):
        if r.closed:
            break
        try:
            await r.send({'type': 'drive', 'linear': 0.3, 'angular': 0.0})
        except tornado.websocket.WebSocketClosedError:
            break
    await until(lambda: r.closed is not None, 5, 'flood_closed')
    rcodes = [f.get('code') or f['type'] for fid, f in r.replies.items() if fid != 'R1']
    w('flood', replies=len(rcodes), spectator=rcodes.count('spectator'),
      rate_limited=rcodes.count('rate_limited'), closed=r.closed)
    check('flooding spectator closed (4403/4429)', r.closed and r.closed[1], lambda c: c in (4403, 4429))
    check('flooding spectator: no command admitted', [c for c in rcodes if c not in
                                                       ('spectator', 'rate_limited')], [])

    w('phase', name='nav_goal')
    check('set_mode auto', await a.ask({'type': 'set_mode', 'mode': 'auto'}), 'ack')
    check('nav_goal', await a.ask({'type': 'nav_goal', 'x': 1.0, 'y': 0.0}), 'ack')
    took = await until(lambda: a.ctl.get('lease') == 'autonomy', 15, 'nav_lease_autonomy')
    check('Nav2 goal running: lease autonomy', took is not None, True)
    check('Nav2 goal running: idle_left_s null', a.ctl.get('idle_left_s'), None)
    await until(lambda: (a.tele['nav'].get('goal') or {}).get('status')
                in ('succeeded', 'aborted', 'canceled'), 120, 'nav_goal_done')
    w('nav_goal_end', goal=a.tele['nav'].get('goal'))
    await until(lambda: a.ctl.get('lease') == 'driver', 5, 'nav_lease_back')
    check('Nav2 goal done: lease back to driver', a.ctl.get('lease'), 'driver')

    w('phase', name='fetch')
    check('select_target', await a.ask({'type': 'select_target', 'colour': COLOUR}), 'ack')
    t_start_tx = time.time()
    check('mission start', await a.ask({'type': 'mission', 'action': 'start'}), 'ack')
    w('mission_start', t=t_start_tx)
    await until(lambda: a.ctl.get('lease') == 'autonomy', 15, 'fetch_lease_autonomy')
    # The driver now sends NOTHING until the mission ends.
    spect_done = False
    peak_input = 0.0
    while True:
        st = a.state()
        li = a.ctl.get('last_input_s')
        if isinstance(li, (int, float)):
            peak_input = max(peak_input, li)
        if not spect_done and st not in (None, 'IDLE', 'COMPLETE', 'ABORT') and peak_input > 90:
            before = st
            check('spectator STOP mid-mission', await b.ask({'type': 'stop'}), 'spectator')
            check('spectator abort mid-mission',
                  await b.ask({'type': 'mission', 'action': 'abort'}), 'spectator')
            await asyncio.sleep(2)
            check('mission unaffected by spectator', a.state() not in ('ABORT',), True)
            w('spectator_mid', state_before=before, state_after=a.state())
            spect_done = True
        if st in ('COMPLETE', 'ABORT') or a.closed:
            break
        if time.time() - t_start_tx > 1500:
            break
        await asyncio.sleep(0.2)
    t_end = time.time()
    m = (a.tele or {}).get('mission') or {}
    w('phase', name='end', state=m.get('state'), result=m.get('result'), reason=m.get('reason'),
      wall_s=t_end - t_start_tx)
    check('fetch terminal state', m.get('state'), 'COMPLETE')
    check('driver kept control through the mission', a.ctl.get('driver_id') == (a.tele or {}).get('you')
          or a.ctl.get('driver') is True, True)
    check('last_input_s exceeded idle_s during autonomy (no faked activity)', peak_input,
          lambda v: v > (a.ctl.get('idle_s') or 60))
    check('spectator mid-mission checks ran', spect_done, True)

    w('phase', name='after_mission')
    back = await until(lambda: a.ctl.get('lease') == 'driver', 10, 'lease_back')
    left = a.ctl.get('idle_left_s')
    check('lease back to driver after the mission', back is not None, True)
    check('a fresh idle window after autonomy', left, lambda v: isinstance(v, (int, float)) and v > 50)
    t_back = time.time()
    rel = await until(lambda: a.ctl.get('last_end') == 'idle_timeout' and not a.ctl.get('driver'),
                      90, 'idle_release_after_mission')
    w('idle_release', after_lease_back_s=(time.time() - t_back) if rel is not None else None)
    check('idle release after the mission', rel is not None, True)
    await until(lambda: (a.tele['platform'].get('stop') or {}).get('latched'), 3, 'latched')
    check('STOP latched after idle release',
          (a.tele['platform'].get('stop') or {}).get('latched'), True)

    w('phase', name='kill')
    check('reclaim', await a.ask({'type': 'claim', 'code': code}), 'ack')
    host('kill')
    await until(lambda: a.closed is not None, 10, 'closed_by_kill')
    check('kill closes the driver', a.closed and a.closed[1], 4403)
    print(f'{sum(RESULTS)}/{len(RESULTS)} checks pass', flush=True)


asyncio.run(main())
