# Measuring the Arena on your phone (`?perf`) — for Gautham

Two M1 acceptance criteria are yours to measure: **phone performance**
(30 fps or better at default detail) and **phone cold start** (first visible
computation within 10 s on mobile data). The agent never marks them done.
`?perf` puts every number you need on the screen, so no USB cable or remote
DevTools is needed.

## Where

The Arena (`?view=arena`) reaches the public site only when the M1 pull
request is merged and Pages deploys. Until then you can measure on Wi-Fi
against your laptop (step B), but **cold start on mobile data needs the
public URL** (step A).

## A. Public site, mobile data (after the M1 merge)

1. On the phone, turn **Wi-Fi off** (mobile data only). Note the network
   type the phone shows (4G / 5G) and the signal bars.
2. Use a **private / incognito tab** each time, so nothing is cached.
3. Open `https://gauthamcodes.github.io/coco-labs/?view=arena&perf`.
4. The panel at the bottom right shows, in milliseconds since you opened
   the link:
   - `Pyodide ready`, `coco_lab ready`, `Arena ready`;
   - `first frame drawn`;
   - `first plan events` (after you tap a goal);
   - `fps` (frames in the last second, and the 95th-percentile frame time);
   - `plan events` received and per second; `step` (model step cost).
5. Wait for `Arena ready`, then tap a goal on the map. Read `first plan
   events`.
6. Let it run for 30 seconds, then read `fps`.
7. Repeat steps 2–6 **five times**. Close the tab completely between runs.
8. Record each run in the table below, with the phone model, browser and
   version, and the network type.

| Run | Network | Pyodide ready | Arena ready | First frame | First plan events | fps (30 s in) | p95 frame ms |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

Phone: ______ Browser and version: ______ Date: ______

**Pass if:** the median `first frame drawn` (or the first visible
computation the attract mode shows) is under 10 s, and `fps` is 30 or more
at default detail. Report the numbers either way; a miss is a result.

## B. Your laptop over Wi-Fi (possible now)

On the laptop, in the canonical checkout's M1 worktree:

```bash
cd lab_web && npm run build
node tools/perf/serve_dist.mjs --port 4174 --host 0.0.0.0
```

Then open `http://<laptop-IP>:4174/coco-labs/?view=arena&perf` on the phone
(same Wi-Fi). This measures the phone's CPU and GPU (fps, step) honestly,
but **not** mobile-data cold start: the files come over your Wi-Fi from the
laptop, gzip-compressed like GitHub Pages.

## Send back

The filled table, phone model, browser, and anything that looked wrong. The
agent records your numbers in `docs/RESULTS.md` as **measured by Gautham**,
with device and conditions, and closes nothing on your behalf.
