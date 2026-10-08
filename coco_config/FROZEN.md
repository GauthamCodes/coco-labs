# coco_config — FROZEN (COCO Lab v2, since 2026-10-08)

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

**What it is and why it is kept:** The single source of truth for robot parameters (wheelbase, radius, masses, joint limits, sensor poses, target regions). Every other package, the Sketch model, Lab 5's limits and v2's planned World Spec (README §5.1, M1.2) read it. v2 READS it; it does not change it.

All engineering rules for it in `CLAUDE.md` still apply (simulator
hygiene, `ros_clean.sh`, never `--fast`, one source of truth for robot
parameters, the acyclic package graph, `cmd_vel_arbiter` as sole wheel
publisher). Its tests stay in `scripts/run_all_package_tests.sh` and must
stay green.
