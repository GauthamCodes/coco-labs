"""Phase 2 Part C: the driver/spectator policy, live, over coco.v1 only.

  probe_session.py OUT URL ORIGIN IDLE_S

Two (later three) browsers-as-scripts against a code-access platform. The
code comes from the HOST (scripts/live_session.sh code), as an interviewer's
would; the kill switch and new session are the host's too. Logs every frame
sent and received, with wall-clock stamps, to OUT (jsonl).
"""
import asyncio
import json
import pathlib
import re
import subprocess
import sys
import time

from tornado.httpclient import HTTPRequest
import tornado.websocket

OUT, URL, ORIGIN, IDLE_S = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
HOST = str(pathlib.Path(__file__).resolve().parents[5] / 'scripts' / 'live_session.sh')
log = open(OUT, 'a', buffering=1)


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


class Client:
    def __init__(self, name):
        self.name, self.n, self.replies, self.tele, self.closed = name, 0, {}, None, None
        self.welcome = None

    async def open(self):
        req = HTTPRequest(URL, headers={'Origin': ORIGIN})
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
            f = json.loads(msg)
            if f['type'] == 'welcome':
                self.welcome = f
            elif f['type'] == 'telemetry':
                self.tele = f
                c = f['platform'].get('control') or {}
                w('tele', who=self.name, control=c,
                  latched=(f['platform'].get('stop') or {}).get('latched'),
                  vel=(f['robot'].get('velocity')),
                  m_state=(f.get('mission') or {}).get('state'))
            elif f['type'] in ('ack', 'error'):
                self.replies[f.get('id')] = f
                w('rx', who=self.name, frame=f)

    async def send(self, frame):
        self.n += 1
        frame = dict(frame, id=f'{self.name}{self.n}')
        w('tx', who=self.name, frame=frame)
        await self.ws.write_message(json.dumps(frame))
        return frame['id']

    async def ask(self, frame, timeout=3.0):
        fid = await self.send(frame)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if fid in self.replies:
                r = self.replies[fid]
                return r.get('code') or 'ack'
            await asyncio.sleep(0.02)
        return 'timeout'

    async def drive(self, seconds, linear=0.2):
        for _ in range(int(seconds * 10)):
            await self.send({'type': 'drive', 'linear': linear, 'angular': 0.0})
            await asyncio.sleep(0.1)
        for _ in range(3):
            await self.send({'type': 'drive', 'linear': 0.0, 'angular': 0.0})
            await asyncio.sleep(0.1)


def check(name, got, want):
    w('check', name=name, got=got, want=want, ok=(got == want))
    print(f'{"PASS" if got == want else "FAIL"} {name}: got {got!r} want {want!r}')


async def until(pred, timeout, label):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            w('cond', label=label, ok=True, after=time.time() - t0)
            return time.time() - t0
        await asyncio.sleep(0.05)
    w('cond', label=label, ok=False, after=timeout)
    return None


async def main():
    code = code_of(host('code'))
    w('phase', name='code', have=bool(code))
    a = await Client('A').open()
    b = await Client('B').open()
    await until(lambda: a.tele and a.tele['robot'].get('localised'), 120, 'localised')
    await until(lambda: a.tele and a.tele['nav'].get('online'), 120, 'nav')

    w('phase', name='spectators')
    check('spectator drive', await b.ask({'type': 'drive', 'linear': 0.2, 'angular': 0.0}), 'spectator')
    check('spectator stop', await b.ask({'type': 'stop'}), 'spectator')
    check('spectator set_mode stop', await b.ask({'type': 'set_mode', 'mode': 'stop'}), 'spectator')
    check('spectator nav_goal', await b.ask({'type': 'nav_goal', 'x': 1.0, 'y': 0.0}), 'spectator')
    check('spectator mission start', await b.ask({'type': 'mission', 'action': 'start'}), 'spectator')
    check('bad code', await b.ask({'type': 'claim', 'code': 'WRONG234'}), 'bad_code')

    w('phase', name='driver')
    check('driver claim', await a.ask({'type': 'claim', 'code': code}), 'ack')
    check('duplicate claim with the right code', await b.ask({'type': 'claim', 'code': code}), 'driver_present')
    check('driver set_mode teleop', await a.ask({'type': 'set_mode', 'mode': 'teleop'}), 'ack')
    w('phase', name='drive_A')
    await a.drive(2.0)
    check('driver stop', await a.ask({'type': 'stop'}), 'ack')

    w('phase', name='idle_wait')
    t_idle0 = time.time()
    took = await until(lambda: a.tele and a.tele['platform']['control'].get('last_end') == 'idle_timeout'
                       and not a.tele['platform']['control'].get('driver'), IDLE_S + 15, 'idle_release')
    w('idle', after=took, since_last_command=time.time() - t_idle0)

    w('phase', name='reclaim_release')
    check('reclaim after idle', await a.ask({'type': 'claim', 'code': code}), 'ack')
    check('set_mode teleop', await a.ask({'type': 'set_mode', 'mode': 'teleop'}), 'ack')
    await a.drive(1.0)
    w('phase', name='release')
    check('release', await a.ask({'type': 'release'}), 'ack')
    check('ex-driver drive after release', await a.ask({'type': 'drive', 'linear': 0.2, 'angular': 0.0}), 'spectator')

    w('phase', name='transfer')
    check('B claims after explicit release', await b.ask({'type': 'claim', 'code': code}), 'ack')
    check('B set_mode teleop', await b.ask({'type': 'set_mode', 'mode': 'teleop'}), 'ack')
    w('phase', name='drive_B')
    await b.drive(1.0, linear=-0.2)
    w('phase', name='B_disconnects_while_driving')
    for _ in range(5):
        await b.send({'type': 'drive', 'linear': 0.2, 'angular': 0.0})
        await asyncio.sleep(0.1)
    b.ws.close()
    await until(lambda: a.tele and a.tele['platform']['control'].get('last_end') == 'driver_disconnected', 5,
                'driver_disconnect_seen')

    w('phase', name='expiry_wait')
    await until(lambda: a.closed is not None, 400, 'expired_closed')
    late = Client('L')
    try:
        await late.open()
        await until(lambda: late.closed is not None, 5, 'late_closed')
        w('late', closed=late.closed, replies=late.replies)
    except Exception as exc:     # noqa: BLE001
        w('late', error=repr(exc))
    host('code')

    w('phase', name='new_session')
    new = code_of(host('new'))
    check('new code differs', bool(new) and new != code, True)
    c = await Client('C').open()
    await until(lambda: c.tele is not None, 10, 'C_tele')
    check('old code in new session', await c.ask({'type': 'claim', 'code': code}), 'bad_code')
    check('new code', await c.ask({'type': 'claim', 'code': new}), 'ack')
    check('C set_mode teleop', await c.ask({'type': 'set_mode', 'mode': 'teleop'}), 'ack')
    w('phase', name='drive_C_then_kill')
    drive = asyncio.ensure_future(c.drive(4.0))
    await asyncio.sleep(1.5)
    w('phase', name='KILL')
    host('kill')
    await until(lambda: c.closed is not None, 5, 'C_closed_by_kill')
    drive.cancel()
    d = Client('D')
    try:
        await d.open()
        await until(lambda: d.closed is not None, 5, 'D_closed')
        w('after_kill', closed=d.closed, replies=d.replies)
    except Exception as exc:     # noqa: BLE001
        w('after_kill', error=repr(exc))
    host('code')
    host('new')
    w('phase', name='end')


if __name__ == '__main__':
    asyncio.run(main())
