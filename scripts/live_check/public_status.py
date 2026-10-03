"""
Render the PUBLIC Live tab in headless Firefox and report its status line.

    public_status.py OUT_DIR [URL]

Default URL: the deployed Pages site's Live view pointed at the Funnel
endpoint. Waits for the status probe to settle (the card first says
"checking"), then records the status words, whether the fallback links
(Replay, Docker quickstart) are shown, the connection label, and a
screenshot. Nothing is clicked: this only reads what a visitor sees.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'browser_check'))
from bidi import Bidi, launch  # noqa: E402

OUT = sys.argv[1]
URL = sys.argv[2] if len(sys.argv) > 2 else (
    'https://gauthamcodes.github.io/coco-labs/?view=live'
    '&live=wss://coco-live.taile7cb60.ts.net/ws')
PORT = 9228


async def main():
    os.makedirs(OUT, exist_ok=True)
    proc = launch(port=PORT, width=1400, height=1000)
    try:
        b = await Bidi.connect(port=PORT)
        await b.cmd('session.new', capabilities={})
        ctx = (await b.cmd('browsingContext.getTree'))['contexts'][0]['context']
        await b.cmd('browsingContext.setViewport', context=ctx,
                    viewport={'width': 1400, 'height': 1100})
        await b.cmd('browsingContext.navigate', context=ctx, url=URL, wait='complete')
        js = '''(() => {
          const t = (id) => { const e = document.querySelector(`[data-testid="${id}"]`);
                              return e ? e.textContent : null; };
          return {status: t('live-status-words'), card: t('live-status'),
                  fallback_links: !!document.querySelector('[data-testid="live-fallback-links"]'),
                  conn: t('live-conn'), badge: t('mode-badge')};
        })()'''
        t0 = time.time()
        seen = None
        while time.time() - t0 < 30:
            seen = await b.eval(ctx, js)
            if seen and seen.get('status') and 'checking' not in (seen.get('card') or ''):
                break
            await asyncio.sleep(0.5)
        await asyncio.sleep(6.0)          # past the probe's 4 s timeout
        seen = await b.eval(ctx, js)
        seen.update(url=URL, at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        await b.shot(ctx, os.path.join(OUT, 'public_status.png'))
        json.dump(seen, open(os.path.join(OUT, 'public_status.json'), 'w'), indent=1)
        print(json.dumps(seen, indent=1))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            proc.kill()


asyncio.run(main())
