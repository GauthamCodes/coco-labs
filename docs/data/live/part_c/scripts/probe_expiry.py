"""Phase 2 Part C: the session cap expiring WHILE the driver is driving.

  probe_expiry.py OUT URL ORIGIN IDLE_S

Claims with the host's code, picks teleop, then drives forward/back at
10 Hz (the page's rate) until the server closes the socket at the cap.
"""
import asyncio
import sys

from probe_session import Client, check, code_of, host, until, w

OUT, URL, ORIGIN = sys.argv[1], sys.argv[2], sys.argv[3]


async def main():
    code = code_of(host('code'))
    a = await Client('A').open()
    await until(lambda: a.tele and a.tele['robot'].get('localised'), 120, 'localised')
    check('driver claim', await a.ask({'type': 'claim', 'code': code}), 'ack')
    check('set_mode teleop', await a.ask({'type': 'set_mode', 'mode': 'teleop'}), 'ack')
    w('phase', name='drive_until_closed')
    sign, n = 1.0, 0
    while a.closed is None:
        n += 1
        if n % 20 == 0:          # 2 s each way: stay near home
            sign = -sign
        try:
            await a.send({'type': 'drive', 'linear': 0.2 * sign, 'angular': 0.0})
        except Exception:        # noqa: BLE001 - the socket closed under us
            break
        await asyncio.sleep(0.1)
    await until(lambda: a.closed is not None, 5, 'closed')
    w('phase', name='end', closed=a.closed)
    await asyncio.sleep(3)
    host('code')


asyncio.run(main())
