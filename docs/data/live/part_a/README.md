# Phase 2 Part A — live audit evidence (2026-10-02)

One run: a fresh simulator, `mission.launch.py rviz:=false platform:=true`
from `~/coco_labs_ws` (main adb7d55), headless, `ROS_DOMAIN_ID=62`, quiet
machine. Report: `docs/live/PART_A_AUDIT.md`.

| file | what |
|---|---|
| `up.sh` | fresh sim + mission stack (mirrors `run_platform.sh --native`) |
| `run_probe.sh` | starts `recorder.py`, runs `probe.py` |
| `probe.py` | coco.v1 client: wait → mission start → teleop preemption → page-style STOP → abort → Nav2 goal → teleop |
| `recorder.py` | wall-clock arrivals on the wheel topic, every arbiter input, `/mission/mode`, `/mission/state`, arbiter status, `/goal_pose`, `/plan`, wheel publisher count |
| `ws.jsonl.gz`, `ros.jsonl.gz` | the two logs (gunzip before analysing) |
| `timings.py`, `analyse.py` | the numbers in the report, and a 0.5 s-bin timeline per phase |
| `sim.log`, `stack.log` | launch output |

Reproduce:

```bash
gazebo_models/scripts/ros_clean.sh          # nothing else may be running
docs/data/live/part_a/up.sh && docs/data/live/part_a/run_probe.sh
python3 docs/data/live/part_a/timings.py docs/data/live/part_a   # after gunzip
gazebo_models/scripts/ros_clean.sh
```

`up.sh` and `run_probe.sh` write logs next to themselves. Copy the directory
somewhere outside the repo before running.
