"""A read-only local spectator that logs what the session does, live.

  session_watch.py OUT SECONDS [URL]

Connects on loopback (default ws://127.0.0.1:8080/ws, so it adds no load
to the tunnel), never claims, never sends a command. Logs every telemetry
frame's session block (driver, driver_id, clients, lease, idle and
session time left, last ending), the latched STOP, the mission state and
reason, the browser Nav2 goal, the arbiter's source and the velocity,
wall-clock stamped. Reconnects if the server closes it.
"""
import asyncio
import json
import sys
import time

from tornado.httpclient import HTTPRequest
import tornado.websocket

OUT, SECONDS = sys.argv[1], float(sys.argv[2])
URL = sys.argv[3] if len(sys.argv) > 3 else 'ws://127.0.0.1:8080/ws'
log = open(OUT, 'a', buffering=1)


def w(kind, **kw):
    log.write(json.dumps({'t': time.time(), 'kind': kind, **kw}) + '\n')


async def main():
    deadline = time.time() + SECONDS
    while time.time() < deadline:
        try:
            ws = await tornado.websocket.websocket_connect(
                HTTPRequest(URL, headers={'Origin': 'http://localhost:4173'}))
        except Exception as exc:  # noqa: BLE001
            w('connect_error', error=repr(exc))
            await asyncio.sleep(2.0)
            continue
        w('open')
        await ws.write_message(json.dumps({'type': 'hello', 'id': 'w',
                                           'client': 'session-watch', 'binary': False}))
        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.read_message(), 5.0)
            except asyncio.TimeoutError:
                continue
            if msg is None:
                w('closed', code=ws.close_code, reason=ws.close_reason)
                break
            if isinstance(msg, bytes):
                continue
            f = json.loads(msg)
            if f.get('type') != 'telemetry':
                if f.get('type') in ('error', 'ack'):
                    w('rx', frame=f)
                continue
            p, m, n, r = f['platform'], f.get('mission') or {}, f['nav'], f['robot']
            w('tele', seq=f.get('seq'), control=p.get('control'),
              latched=(p.get('stop') or {}).get('latched'),
              arbiter=(p.get('arbiter') or {}).get('active'),
              pilot=p.get('pilot'), m_state=m.get('state'), m_result=m.get('result'),
              m_reason=m.get('reason'), goal=n.get('goal'), vel=r.get('velocity'),
              localised=r.get('localised'))
        ws.close()


asyncio.run(main())
