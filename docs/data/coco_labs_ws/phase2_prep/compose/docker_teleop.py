"""
Teleop through the shipped page against COCO running in Docker.

    python3 docker_teleop.py <url> <outdir>

One W drive, one S drive, and one STOP clicked while W is still held --
real key presses and a real click in headless Firefox, through the same
bidi.py that scripts/browser_check/live.py uses. Writes <outdir>/actions.json.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, '/home/gautham/coco_labs_ws/src/coco-labs/scripts/browser_check')
from bidi import Bidi, launch  # noqa: E402

URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
ACTIONS = []
READ = '''(() => { const t = (id) => { const e = document.getElementById(id);
  return e ? (e.hidden ? '[hidden]' : e.textContent.trim()) : '[missing]'; };
  return { conn: t('connState'), health: t('healthChip'), pose: t('poseRead'),
    vel: t('velRead'), src: t('srcRead'), lifecycle: t('lifecycleRead'),
    healthRead: t('healthRead') }; })()'''


def act(name, **extra):
    row = {'t': round(time.time(), 4), 'action': name, **extra}
    ACTIONS.append(row)
    print(json.dumps(row), flush=True)
    with open(os.path.join(OUT, 'actions.json'), 'w') as handle:
        json.dump(ACTIONS, handle, indent=1)


async def unfocus(b, ctx):
    await b.eval(ctx, 'document.activeElement && document.activeElement.blur(); 1')


async def hold(b, ctx, key, seconds, label):
    await unfocus(b, ctx)
    act(f'{label}_down', key=key)
    await b.keys(ctx, [{'type': 'keyDown', 'value': key},
                       {'type': 'pause', 'duration': int(seconds * 1000)},
                       {'type': 'keyUp', 'value': key}])
    act(f'{label}_up', key=key)


async def main():
    proc = launch(width=1400, height=1000)
    b = await Bidi.connect()
    await b.cmd('session.new', capabilities={})
    await b.cmd('session.subscribe', events=['log.entryAdded'])
    ctx = (await b.cmd('browsingContext.getTree'))['contexts'][0]['context']
    await b.cmd('browsingContext.setViewport', context=ctx,
                viewport={'width': 1400, 'height': 1000})
    await b.cmd('browsingContext.navigate', context=ctx, url=URL, wait='complete')
    try:
        t0 = time.time()
        state = await b.eval(ctx, READ)
        while time.time() - t0 < 300 and state['conn'] != 'Ready':
            await asyncio.sleep(0.5)
            state = await b.eval(ctx, READ)
        act('page_ready', seconds=round(time.time() - t0, 2), state=state)
        if state['conn'] != 'Ready':
            return 1
        await b.click_id(ctx, 'modeTeleop')
        await asyncio.sleep(0.5)
        await hold(b, ctx, 'w', 2.0, 'drive_forward')
        await asyncio.sleep(1.5)
        await hold(b, ctx, 's', 2.0, 'drive_back')
        await asyncio.sleep(1.5)
        await b.shot(ctx, os.path.join(OUT, 'after_drive.png'))
        # STOP with W still held.
        await unfocus(b, ctx)
        act('stop_test_w_down')
        await b.keys(ctx, [{'type': 'keyDown', 'value': 'w'}])
        await asyncio.sleep(1.5)
        await b.click_id(ctx, 'estop')
        act('stop_clicked_w_still_held')
        await asyncio.sleep(2.5)
        await b.keys(ctx, [{'type': 'keyUp', 'value': 'w'}])
        await b.cmd('input.releaseActions', context=ctx)
        act('stop_test_w_up', state=await b.eval(ctx, READ))
        errs = [e['params'].get('text') for e in b.events
                if e.get('method') == 'log.entryAdded'
                and (e['params'].get('level') == 'error'
                     or e['params'].get('type') == 'javascript')]
        act('js_errors', errors=errs)
        return 0
    finally:
        import signal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


sys.exit(asyncio.run(main()))
