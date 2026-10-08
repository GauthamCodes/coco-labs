<!-- Published GitHub release text as fetched with `gh release view live-v1.0` on 2026-10-08, before the M0 fix A.4 wording edit. Metadata (must be unchanged after): {"tagName": "live-v1.0", "isDraft": false, "isPrerelease": false, "targetCommitish": "4530a8b867e89dbf641790903ece7888e08b05f4", "publishedAt": "2026-10-04T18:17:00Z", "assets": []} -->

# Title

COCO Live — the real robot in the browser (v1.0)

# Body

**Try it:** https://gauthamcodes.github.io/coco-labs/?view=live · a public
session is on only when the owner schedules one; otherwise the page says so
and links Replay and the Docker quickstart.

**COCO Live** (Phase 2): the Live tab of COCO Lab drives the simulated COCO
robot running the real ROS 2 / Nav2 stack, in three modes: **teleop**,
**Nav2 goal**, and the **autonomous fetch**. It works against a stack on
your own machine (Docker), or, during a scheduled public session, against
the owner's machine through a Tailscale Funnel tunnel. Write-up, runbook,
evidence and limitations:
[`docs/live/LIVE.md`](https://github.com/GauthamCodes/coco-labs/blob/live-v1.0/docs/live/LIVE.md).

### What shipped

- **The browser speaks `coco.v1` and names intents, never topics.** The
  server maps each intent to an allowlisted publisher.
- **One wheel publisher:** `cmd_vel_arbiter`, which lets teleop preempt
  autonomy. Nothing in Live publishes to the wheels.
- **Remote sessions:** one driver per host-issued 8-character code;
  spectators are refused every command; per-client rate limits; a 20-minute
  session cap and a host kill switch. Only `/ws` and `/healthz` are public.
- **Safety:** a latched STOP on STOP, on a driver disconnect, after 60 s
  idle, at the session cap and on the kill switch; the 0.5 s wheel
  watchdog underneath.
- **Ground truth is display-only**: it never reaches anything that
  commands.

### Measured (details in `docs/live/LIVE.md` §7 and `docs/live/PART_C_REPORT.md`)

| | value |
|---|---|
| local: drive frame → wheel | p50 4.6 ms, max 9.7 ms (n = 170) |
| local: STOP → wheel zero; fetches from the page | 6.2 ms; 3 / 3 COMPLETE |
| Docker remote configuration: fetch | red COMPLETE, 16 states, 0 recoveries |
| through Funnel (host as client): drive → wheel; STOP → zero; goal → plan | p50 45.2 ms (n = 170); 148.4 ms; p50 153.3 ms, goals 5 / 5 |
| through Funnel: delivered throughput; app RTT | ≈ 58 KiB/s ceiling; p50 0.56–1.46 s, max 8.3 s |
| phone on mobile data: driver disconnect → robot at rest | 0.54 s from 0.3 m/s, mission aborted `OPERATOR_ABORT`, 0 moving commands after |
| phone page readouts | RTT ≈ 282–293 ms, telemetry 5 Hz (**owner-reported**) |
| exposure | no non-loopback TCP listener; externally only `/ws` and `/healthz` |

### Tests

`run_all_package_tests.sh` **2,691 passed, 0 failed** (11 packages); lab_web
vitest **238**, `tsc`, build and `check_dist` clean. `CI` and `Lab` green on
this tag's commit `4530a8b` on `main` (runs 37147633298 and 37147633295,
the latter deploying it to Pages).

### Known limitations

- **Funnel is DERP-relayed here:** about 58 KiB/s, a view that lags by
  seconds, and a 10 s keepalive that dropped a connection 2 times in
  407 s (measured). Each drop stops COCO and needs a re-claim.
- **Phone-test gaps:** STOP from the phone, a second-device spectator,
  preemption from the phone, a completed mission from the phone, and the
  cause of the phone's disconnect are not in the record.
- The browser goal's status did not show its preemption by a mission's
  goal (34 s of `executing`).
- Spectators cannot STOP; the host's kill switch is the backstop.
- The Pages origin admits every page under `https://gauthamcodes.github.io`
  (an Origin has no path).
- The image base is pinned by tag, not digest.
- Opening the public Pages site against a *local* stack is unverified
  (browsers may block an https page reaching `ws://localhost`).
- The autonomous mode is **told** the target's lane; discovery is a later
  phase. The page says so.
- Not built from ROADMAP §3.5: planner choice in Nav2 mode, a `nav_goal`
  heading, the 3D view.

### Video

None. Recording a live session needs the stack and the tunnel up, which is
the owner's call; no Phase 2 video exists.

(The public site is now built from a later commit that adds Lab 2; the Live
tab's code, `lab_web/src/live` and `coco_web`, is unchanged since this tag.)

