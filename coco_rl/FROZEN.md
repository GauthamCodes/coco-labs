# coco_rl — FROZEN (COCO Lab v2, since 2026-10-08)

This package is part of the **COCO robot stack** that lives inside the
`coco-labs` repository. Under the COCO Lab v2 master plan
([`README.md`](../README.md) §4, "Robot-stack ROS packages inside
`coco-labs` — Freeze") it is:

- **Kept.** Nothing in it is deleted. The Live Stack (simulated) and the
  recorded STACK evidence (Labs 1–5, `~/coco_lab_runs/`, `docs/data/`)
  depend on it.
- **Closed to new features.** Bug fixes that keep Live, the recordings or
  the test suite working are allowed, each with its own evidence; new
  behaviour is not. A change here needs the milestone, checkpoint and exit
  criterion it serves (the drift test, `CLAUDE.md`).
- **Awaiting decision G3** ("canonical robot stack", README §8). Until
  Gautham decides, the default holds: the COCO robot repository is
  canonical, and these packages are frozen, not deleted.

**What it is and why it is kept:** The shipped ramp policy (`policies/phase5_24deg_s0p0.zip`), its training and evaluation code, the classical baselines, the terrain observer, and the Docker build-context checks. The mission's CLIMB runs this policy. RL is not COCO Lab teaching material (README §6: deferred).

All engineering rules for it in `CLAUDE.md` still apply (simulator
hygiene, `ros_clean.sh`, never `--fast`, one source of truth for robot
parameters, the acyclic package graph, `cmd_vel_arbiter` as sole wheel
publisher). Its tests stay in `scripts/run_all_package_tests.sh` and must
stay green.
