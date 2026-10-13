# Measuring the Arena on your phone (`?perf`) — for Gautham

Two M1 acceptance criteria are yours to measure: **phone performance**
(30 fps or better at default detail) and **phone cold start** (first visible
computation within 10 s on mobile data). The agent never marks them done.
`?perf` puts every number you need on the screen, so no USB cable or remote
DevTools is needed.

## Where (updated 2026-10-11, after the M3 merge)

**Everything below is live on the public site now**: M1, M2 and M3 are merged
(`main` = `bf7443f`, deployed by GitHub Pages). Decision D5: the **phone
baseline is measured now, on the live site** — sections A, M2 and M3 below,
on mobile data. Record the results where "Send back" says; the agent adds
them to `docs/RESULTS.md` as measured by Gautham and lists them in
`docs/STATUS.md`. M4's own phone rows come later, in `docs/v2/PHONE_GATE_M4.md`.

## A. Public site, mobile data

1. On the phone, turn **Wi-Fi off** (mobile data only). Note the network
   type the phone shows (4G / 5G) and the signal bars.
2. Use a **private / incognito tab** each time, so nothing is cached.
3. Open `https://gauthamcodes.github.io/coco-labs/?view=arena&perf`.
4. The panel (top of the screen on a phone) shows, in milliseconds since
   you opened the link:
   - `recording ready (attract)` and **`first computation shown`**: the
     page opens on a recorded demo (labelled MODEL) and draws its search
     before the live model has loaded. **This is the cold-start number**:
     the first visible computation;
   - `Pyodide ready`, `coco_lab ready`, `Arena ready` (the live model);
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

| Run | Network | First computation shown | Arena ready | First frame | First plan events | fps (30 s in) | p95 frame ms |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

Phone: ______ Browser and version: ______ Date: ______

**Pass if:** the median `first computation shown` is under 10 s on mobile
data (phone cold start), and `fps` is 30 or more at default detail (phone
performance). Report the numbers either way; a miss is a result.

## B. Your laptop over Wi-Fi (possible now)

On the laptop, in the canonical checkout (`~/coco_labs_ws/src/coco-labs`,
fast-forwarded to `main`):

```bash
cd lab_web && npm ci && npm run build
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

## M2: the fetch mission and the lenses (after the M2 merge)

M2's phone rows (M2 prompt, B.3): **at least 30 fps at default detail on the
fetch mission**, and **first visible computation within 10 s on mobile
data** (step A above measures the second; nothing about it changed). For the
first:

1. Mobile data or Wi-Fi, a private tab, open
   `https://gauthamcodes.github.io/coco-labs/?view=arena&perf&lens=decide`.
2. Wait for `Arena ready`, then tap **Start the fetch** (the Decide lens's
   controls). The robot chooses a bay, drives, looks, grasps and comes home
   (about 2.5 minutes).
3. While it drives to its first bay, read `fps` and the p95 frame time; read
   them again while it drives home.
4. Then tap **Localise**, **Map** and **Move** in turn and note, for each,
   whether the controls appeared within about 3 s (the laptop budget is 3 s
   with a warm cache; the phone has none, so just note it), and the `fps`
   with that lens's layers on.
5. Repeat steps 1–3 **three times**.

| Run | Network | fps (to the bay) | p95 ms | fps (home) | p95 ms | Localise / Map / Move: controls within ~3 s? fps |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |

Phone: ______ Browser and version: ______ Date: ______

**Pass if** the fetch mission's median `fps` is 30 or more. The laptop's
numbers for the same scene (with a heavier stress load on top) are in
`docs/v2/M2_RESULTS.md`; they say nothing about a phone.

## M3: Play, the Case Files and the four modes (after the M3 merge)

M3's phone row (M3 prompt, B.3) is the same cold start as before: **a cold
visitor sees computation within 10 s on a mid-range phone over mobile
data** (step A). Measure it again on the M3 site: the landing page now also
carries the mode bar. The steps below are what M3 added; note them while you
are there.

1. **Case Files** (mobile data, a private tab):
   `https://gauthamcodes.github.io/coco-labs/?view=arena&casefile=lab5_mislocalised_dwb_1&perf`.
   **The `?perf` panel does not show a Case File's own load time** on the
   live site: its "recording ready (attract)" row is the attract demo's, not
   the Case File's — do not record it as the Case File. Note by eye how long
   until the recorded robot and the timeline appear, and whether the LiDAR
   rays appear a moment later (since the M3 review, decision D6, a Case File
   draws its first frame before its scans arrive). The agent's measurement on
   emulated 4G: 100 / 100 Case Files within 2 s, worst 1.83 s
   (`docs/v2/reviews/M3_REVIEW.md`). Then drag the timeline back and forth:
   does it follow your finger?
2. **Play**: `?view=play&c=beat-the-planner&l=bog`. Note how long until the
   grid appears: that is the scorer loading, Pyodide and coco_lab. Draw a
   path by tapping cells, then press **Score my path**. Can you tap one cell
   at a time? Is the result readable without zooming?
3. **The four modes**: tap Learn, Play, Sandbox and Case Files in turn. For
   each, note whether anything is cut off or scrolls sideways, and whether
   the MODEL / STACK badge is visible without scrolling.
4. Repeat step 1 **three times**, closing the tab completely between runs.

| Run | Network | Case File on screen after (by eye) | Timeline follows the finger? | Play: grid shown after | Tapping cells OK? | Modes: anything cut off? |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |

Phone: ______ Browser and version: ______ Date: ______

**Pass if** the cold start (step A) is under 10 s. The rest are notes; the
agent turns anything that looked wrong into a line in `docs/IDEAS.md`. The
agent's emulated-phone checks at 390 px are in `docs/v2/data/m3/m37/`: they
measure the layout, not a phone.
