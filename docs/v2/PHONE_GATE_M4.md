# M4 feasibility gate on your phone — for Gautham

M4's first checkpoint asks one question: **can a phone hold the 3D Arena?**
Your answer sets one switch, the camera phones open on (decision D1):
`PHONE_DEFAULT_CAMERA` in `lab_web/site.config.ts`, now `'3d'`. If the phone
fails the gate, phones default to the top-down view and desktops stay 3D.
The milestone does not wait for you; the agent applies your result whenever
you record it. **The agent never marks these rows done.**

Evidence class of what you record: **MODEL** (the browser), measured by
you, with the device and the network written next to it. The agent's own
numbers under phone-like conditions are **emulated**, never "phone"
(`docs/v2/data/m4/m41/`).

## Where to open it

The 3D Arena is on the M4 branch, not yet on the public site. Two ways:

**A. The phone preview over mobile data (preferred).** The agent (or you)
runs, on the laptop:

```bash
lab_web/tools/preview_phone.sh start      # builds, serves, prints the URL; off by itself after 2 hours
lab_web/tools/preview_phone.sh stop       # or stop it now
```

It prints a URL of the form
`https://coco-live.<your-tailnet>.ts.net/coco-labs/?view=arena&camera=follow&perf`.
It serves this branch's static build only, gzip-compressed like GitHub
Pages, on the path `/coco-labs/` only. It cannot run while Live's tunnel is
up (the same Tailscale node), and Live's `/ws` and `/healthz` are not
served by it. When it started, the agent records the URL and the time it
turns off in `docs/STATUS.md`.

**B. Over Wi-Fi from the laptop (if Funnel is unavailable).** `cd lab_web
&& npm run build && node tools/perf/serve_dist.mjs --port 4174 --host
0.0.0.0`, then `http://<laptop-IP>:4174/coco-labs/?view=arena&camera=follow&perf`.
This measures the phone's GPU and CPU honestly, but **not** cold start on
mobile data.

## What to measure

Use a **private / incognito tab** each time (an empty cache is what makes a
start cold), Wi-Fi **off** for A. Note the phone, the browser and its
version, the network (4G / 5G, bars).

1. **Cold start** (README §7 M4: first visible computation ≤ 10 s on
   mobile data; 3D world interactive ≤ 15 s). Open the URL. In the `?perf`
   panel read:
   - **`first computation shown`** — the first visible computation;
   - **`Arena ready`** — the live model;
   - the time the 3D world appears with the robot in it (until M4.4 adds a
     `3D world ready` row to the panel, note it by eye: count seconds from
     the tap that opened the link).
   Close the tab completely; repeat **five times**.
2. **Frame rate over 10 minutes** (≥ 30 fps on the automatic tier with the
   world and default layers). In one tab: tap a goal on the floor, let
   COCO drive; tap another goal whenever it arrives, for **10 minutes**.
   Read `fps` and the p95 frame time at 1, 5 and 10 minutes. Note any
   reload, crash, blank or frozen canvas (context loss).
3. **Touch feel.** Drag one finger to orbit the camera, pinch to zoom, tap
   the floor to set a goal. Does the camera respond immediately? Does a
   tap on the floor put the goal where you tapped? Anything uncomfortable
   to watch (motion discomfort)? *(The joystick, tank mode and their
   ~100 ms `?perf` reading arrive with M4.5; until then, note the feel.)*

## Record it here, then in STATUS

| Run | Network | First computation shown | Arena ready | 3D world on screen (by eye) |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |

| Minute | fps | p95 frame ms | Anything wrong? |
|---|---|---|---|
| 1 | | | |
| 5 | | | |
| 10 | | | |

Touch feel (orbit, pinch, tap-to-goal, discomfort): ______

Phone: ______ Browser and version: ______ Date: ______

Send the tables back, or paste them under **"Pending Gautham → M4
feasibility gate"** in `docs/STATUS.md`. The agent then records them in
`docs/RESULTS.md` as **measured by Gautham**, and applies D1:

- **Pass** (median fps ≥ 30 over the 10 minutes, cold start within the
  budgets above, no crash or context loss): `PHONE_DEFAULT_CAMERA` stays
  `'3d'`.
- **Fail** on frame rate or stability: `PHONE_DEFAULT_CAMERA` becomes
  `'topdown'` in one commit, and the plan-change log says so. A slow cold
  start alone is a budget miss to work on (assets, attract mode), not a
  reason to drop 3D.

## What the preview is and is not

- It is the **feasibility build** (M4.1): a first, rough conversion of the
  arena and the robot, the follow camera, the Plan lens on the floor,
  flat lighting. It is not the look M4 ships (M4.4), and there is no
  terrain yet (M4.3: the robot does not climb the ramps).
- `?camera=follow` opens it in 3D; without it the page opens top-down, as
  the public site does today. `?camera=orbit` and `?camera=robot_eye` also
  work (the robot-eye view is a rendered presentation, not the robot's
  perception).
