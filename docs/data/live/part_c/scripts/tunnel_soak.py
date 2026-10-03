"""Hold one coco.v1 connection through the public URL; log rate and closes.

  tunnel_soak.py OUT URL SECONDS [camera]

Spectator only (no claim, no commands). Records every received frame's
type and size with a wall-clock stamp, the connection's close code and
reason, and reconnects to count how often a connection dies. With
`camera`, it declares binary and subscribes to the camera stream, as the
Live tab does.
"""
import asyncio
import json
import ssl
import sys
import time

from tornado.httpclient import HTTPRequest
import tornado.websocket

OUT, URL, SECONDS = sys.argv[1], sys.argv[2], float(sys.argv[3])
CAMERA = 'camera' in sys.argv[4:]
log = open(OUT, 'a', buffering=1)


def w(kind, **kw):
    log.write(json.dumps({'t': time.time(), 'kind': kind, **kw}) + '\n')


async def one(deadline, n):
    req = HTTPRequest(URL, headers={'Origin': 'http://localhost:4173'},
                      ssl_options=ssl.create_default_context())
    t0 = time.time()
    ws = await tornado.websocket.websocket_connect(req, ping_interval=None)
    w('open', n=n, after=time.time() - t0)
    await ws.write_message(json.dumps({'type': 'hello', 'id': 'h', 'client': 'soak',
                                       'binary': CAMERA}))
    if CAMERA:
        await ws.write_message(json.dumps({'type': 'subscribe', 'id': 's',
                                           'streams': ['camera']}))
    counts, sizes = {}, {}
    while time.time() < deadline:
        try:
            msg = await asyncio.wait_for(ws.read_message(), max(0.1, deadline - time.time()))
        except asyncio.TimeoutError:
            break
        if msg is None:
            w('closed', n=n, code=ws.close_code, reason=ws.close_reason,
              lived=time.time() - t0, counts=counts, bytes=sizes)
            return False
        if isinstance(msg, bytes):
            kind = 'binary'
        else:
            kind = json.loads(msg).get('type')
            if kind == 'error':
                w('error_frame', frame=json.loads(msg))
        counts[kind] = counts.get(kind, 0) + 1
        sizes[kind] = sizes.get(kind, 0) + len(msg)
        if kind == 'telemetry':
            w('tele', n=n)
    w('end', n=n, lived=time.time() - t0, counts=counts, bytes=sizes)
    ws.close()
    return True


async def main():
    deadline = time.time() + SECONDS
    n = 0
    while time.time() < deadline:
        n += 1
        try:
            if await one(deadline, n):
                break
        except Exception as exc:  # noqa: BLE001
            w('connect_error', n=n, error=repr(exc))
            await asyncio.sleep(1.0)
    tele = [json.loads(line) for line in open(OUT) if '"tele"' in line]
    closes = [json.loads(line) for line in open(OUT) if '"closed"' in line]
    span = (tele[-1]['t'] - tele[0]['t']) if len(tele) > 1 else 0
    print(f'connections {n}; closes {len(closes)}: '
          f'{[(c["code"], c["reason"], round(c["lived"], 1)) for c in closes]}; '
          f'telemetry {len(tele)} frames over {span:.1f} s = '
          f'{(len(tele) - 1) / span if span else 0:.2f} Hz')


asyncio.run(main())
