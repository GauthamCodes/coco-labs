"""Phone-width render of the Live tab against fakestack; layout checks."""
import asyncio
import json
import sys

sys.path.insert(0, '/home/gautham/ros2_ws(personal)/src/coco-robot-ros2/.claude/worktrees/lab1/scripts/browser_check')
from bidi import Bidi, launch  # noqa: E402

OUT = sys.argv[1]
URL = 'http://localhost:4174/coco-labs/?view=live&live=ws://127.0.0.1:8090/ws'


async def main():
    proc = launch(port=9227, width=390, height=844)
    try:
        b = await Bidi.connect(port=9227)
        await b.cmd('session.new', capabilities={})
        ctx = (await b.cmd('browsingContext.getTree'))['contexts'][0]['context']
        await b.cmd('browsingContext.setViewport', context=ctx,
                    viewport={'width': 390, 'height': 844})
        await b.cmd('browsingContext.navigate', context=ctx, url=URL, wait='complete')
        await asyncio.sleep(5)
        await b.shot(ctx, f'{OUT}/phone_top.png')
        report = await b.eval(ctx, '''(() => {
          const s = document.querySelector('[data-testid="live-stop"]');
          const r = s.getBoundingClientRect();
          const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
          return {stopHit: hit === s, stopBox: [r.left, r.top, r.width, r.height],
                  hScroll: document.documentElement.scrollWidth > window.innerWidth,
                  scrollWidth: document.documentElement.scrollWidth, inner: window.innerWidth,
                  conn: document.querySelector('[data-testid="live-conn"]').textContent,
                  badge: document.querySelector('[data-testid="mode-badge"]').textContent};
        })()''')
        await b.eval(ctx, 'document.querySelector(\'[data-testid="live-joystick"]\').scrollIntoView({block:"center"})')
        await asyncio.sleep(0.5)
        await b.shot(ctx, f'{OUT}/phone_stick.png')
        print(json.dumps(report))
    finally:
        proc.terminate()


asyncio.run(main())
