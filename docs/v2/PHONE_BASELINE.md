# Phone baseline — how to measure v1 on your phone (M0.3)

The laptop numbers are in [`BASELINE.md`](BASELINE.md). On the laptop
every view holds 60 fps, so the phone is the device that decides v2's
budgets (M1: "30 fps or better on Gautham's phone", "first visible
computation within 10 s on mobile data"). This page lets you take the same
two measurements — **Pyodide cold start** and **warm map edit** — on your
phone, and record them. Evidence class of what you record: **MODEL**
(the browser), with the device and network written next to it.

**What to measure on:** the public site,
<https://gauthamcodes.github.io/coco-labs/>. It is built from `main` =
`2b6f8ad`, and the only commits between it and `coco-lab-v1-final`
(`3571169`) are documentation, so the site's code is the one the laptop
baseline measured.

## The flow (identical to the laptop's)

1. Open a **new private / incognito tab** (empty cache — that is what makes
   the first edit cold).
2. Go to
   `https://gauthamcodes.github.io/coco-labs/?view=plan&perf&bundle=arena_0_10m`
   and wait for the arena to draw.
3. Tap **Paint wall** (the paint tool), brush 1 × 1 (the default).
4. Tap **one free cell** near the middle of the map. The status line says
   "Loading Python (Pyodide …)". Wait for **"Done: …"**. That was the
   **cold** edit.
5. Tap three more free cells, **one at a time**, each time waiting for
   "Done". Those are the three **warm** edits.
6. Repeat steps 1–5 four more times (five runs), each in a **new** private
   tab. Close the old tab first.

Do it once on **mobile data** (the M1 criterion) and, if you like, once on
Wi-Fi. Write down which.

## Method A — exact, with remote DevTools (recommended)

This reads the page's own timers, so the numbers compare directly with the
laptop's.

**Android + Chrome:**
1. Phone: Settings → About phone → tap *Build number* 7 times (Developer
   options); Developer options → **USB debugging** on.
2. Connect the phone to the laptop by USB; allow the prompt on the phone.
3. Laptop Chrome/Chromium: open `chrome://inspect/#devices`, find the
   phone's tab, click **inspect**.
4. Before step 4 of the flow, paste the whole of
   [`lab_web/tools/perf/phone_marks.js`](../../lab_web/tools/perf/phone_marks.js)
   into that DevTools **Console** and press Enter. It answers "Recording".
5. Do the four edits. The console prints `edit 1: … ms (COLD)` and three
   `(warm)` lines. `window.__m0phone` holds the list.

**iPhone + Safari:** iPhone Settings → Safari → Advanced → **Web
Inspector** on; connect to a Mac; Mac Safari → Develop → *your iPhone* →
the tab; paste the same script into its Console. (Needs a Mac; if you have
none, use Method B.)

## Method B — no cable

After each edit the status line itself prints the time spent inside the
browser, e.g.
`Done: painting and searching again. coco_lab: 1 search 777 ms, load 419 ms, write 544 ms · first start: Pyodide 39736 ms, install 632 ms`.

- **Cold**: copy the whole "Done" line of edit 1 (the "first start:
  Pyodide … ms, install … ms" part is the cold-start cost).
- **Warm**: copy the "Done" line of edits 2–4 (search + load + write is
  the work; it excludes decode and drawing, so it reads **lower** than
  Method A).

Optionally screen-record the phone while tapping and count frames from the
tap to the path redraw (±1 frame of the recording, ~33 ms at 30 fps).

## Results — fill this in

Phone model: ________ · OS / browser + version: ________ ·
Network: mobile data / Wi-Fi (operator, signal): ________ ·
Date and time: ________ · Method: A / B

| run | cold edit 1 (ms) | warm edit 2 (ms) | warm edit 3 (ms) | warm edit 4 (ms) | status line of edit 1 (Method B) |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
| **median (range)** | | | | | |

Laptop, for comparison (`BASELINE.md` §1, Method A equivalent): cold
median 12,857 ms (6,567–42,882), warm median 1,445 ms (1,265–1,686).

Once filled, commit this file with the table and add one line to
`docs/RESULTS.md` under "COCO Lab v2 · M0 baseline" citing it. Until then
the phone numbers are **not yet measured**.
