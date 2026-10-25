# G2.8 — the real phone, after Rules 5, Fetch by colour and the hotfix (2026-10-25)

**MEASURED on the real device.** Nothing Phone (1) (A063), Chrome, full screen, **medium tier
(shipped default)**, pixel ratio 1.25, on AC; served by the laptop over USB (`adb reverse`) from a
frozen copy of the build; `lab_web/tools/phone/real_phone_free.mjs` (no DevTools while playing;
Android input only). Rotation settings restored to 0 / 0 after every run (`settings_restored`);
COCO's saved settings on the phone's usual origin were not touched (each build on a fresh port).
Screenshots (status bar blacked out): [`../../../screens/g28/real_phone_final/`](../../../screens/g28/real_phone_final/).
Gazebo ran on the laptop during these runs (the phone renders on its own GPU; the laptop only serves
static files).

| Run | Build | fps median / min / p05 | frame p99 / max | > 50 ms | lost | battery °C | skin °C | GPU °C |
|---|---|---|---|---|---|---|---|---|
| GAME, Free Drive (Depot), 10 min | d739127 + Race Nav2 colour wiring (before the /rosout fixes) | 60 / 41 / 60 | 21.2 / 74.0 ms | 3 of 35,961 | 0 | 33 → 40 | 32.1 → 41.5 | 36.6 → 59.0 |
| SIM, Fetch Rush seed 1, 2 min | same | 60 / 60 / 60 | 20.5 / 29.6 ms | 0 of 7,200 | 0 | 40 → 39 | 41.1 → 40.9 | 54.8 → 58.3 |
| SIM, Fetch Rush seed 1, 2 min | + /rosout stops before the strip | 60 / 56 / 60 | 19.8 / 49.9 ms | 0 of 7,196 | 0 | 38 → 39 | 39.4 → 40.2 | 50.5 → 57.1 |
| SIM, Fetch Rush seed 1, 1 min | + clamp on the text (final layout) | 60 / 60 / 60 | 21.4 / 27.7 ms | 0 | 0 | 38 → 38 | — | — |
| **GAME, Free Drive (Depot), 10 min** | **final layout** | **60 / 46 / 59** | **23.9 / 91.2 ms** | **14 of 35,864** | **0** | 39 → 41 | 40.6 → 43.2 | 56.3 → 60.2 |

Only the first run started cool (battery 33 °C, the ≤ 36 °C rule); the others followed it and
started warm. The final GAME run ended at a 758 × 361 viewport (803 × 361 in the others): Android's
navigation bar was probably showing; reported as measured.

**Touch-to-motion: still UNRESOLVED.** Medians 118–207 ms, p90 3.75–4.94 s (the >1 s clusters of
G2.8's first phone runs remain).

**Two layout defects the phone found, fixed** (`../rosout_room/`): the collapsed /rosout line ran
under the fixed-width telemetry strip (12 px at this size), and showed the top of a third line
through its padding. The last two rows are on the fixed build; their screenshots show two lines,
clear of the strip.

**A discarded run.** One SIM run measured the wrong build: the port chosen (4190) was already held
by an older server (the hotfix worktree, main's G1 look) and the new server failed to start, so the
phone loaded that page. Its numbers are not reported; the run was repeated on a verified port.
