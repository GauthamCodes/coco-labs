# Grasp Assist — the model side (M6F.5)

README §5.8. Badge **MODEL · MoveIt-style**: deterministic, kinematic, no forces, no
MoveIt. Code `coco_lab/coco_lab/grasp_assist.py` (the Arena subsystem `assist`); events
`coco.manip.grasp.*` (`coco_schemas/proto/coco/manip/v1/grasp.proto`) and the arm on
`coco.arm.state.v1`. Tests `coco_lab/test/test_grasp_assist.py`,
`coco_lab_ros/test/test_m6f_constants.py`, `coco_lab_ros/test/test_m6f_manip_schema.py`.
No UI here: the visuals are M6 UI-phase work.

## Inputs

`config` inputs, so a session's input log replays it: `assist.grasp=go` (the G button:
pick, or release what is carried), `assist.target=<object id>|any`, `assist.abort=1`.
The subsystem exists only on a World Spec v3 level. STOP, a person's teleop or a goal
click ends an attempt (STOP > the person > assists, invariant 3); the assist drives
as autonomy (`mode='teleop'` with `user_teleop` false, as the mission backs up), so the
command source reads `mission`, never the person.

## The pipeline, stage by stage

| Stage | What happens | Numbers (all existing constants or measured evidence) |
|---|---|---|
| detect | every placed object the camera sees (within range, inside the horizontal FOV, line of sight not crossing a solid other than what the object stands on) or that lies within a short radius in any direction | camera FOV 1.25 rad and x 0.125 m (`coco_config.robot.CAMERA_HFOV`, `CAMERA_XYZ`, pinned); range **1.40 m: the measured first-detection distance of the 20 mm target** (`docs/data/p03c_episode_gazebo/README.md`, STACK); short radius = `grasp.APPROACH_RANGE` 0.6 m |
| check | `too_wide`, `out_of_reach`, `not_magnetic` from the object; `blocked` when no approach heading is free | see `DEPOT_DESIGN.md`'s envelope table; 16 headings |
| choose | the pickable object with the cheapest approach: the A\* path length from the robot's belief to the free pre-grasp pose nearest it that a path reaches; refused objects rank after, by distance | |
| approach | the Arena's planner to the pre-grasp pose (`request_goal`), the waypoint follower (the local controller) driving | standoff = `grasp.APPROACH_RANGE` − `sketch.WAYPOINT_TOL` = 0.48 m |
| align, creep | turn to face the object, then creep into the window, with the gated grasp's own law | `grasp.TURN`, `CREEP`, `ALIGNED`, `SETTLED`, `MAX_CREEPS`; the gate `grasp.WINDOW` 0.151–0.1565 m, `grasp.MAX_LATERAL` 10 mm |
| reach | IK (`arm.ik`) at the object's grasp band and at the hover above it, the solution nearest pick_place.py's verified pose; the joint trajectory is `arm.GRASP_SCRIPT`'s phases and durations with those poses | `arm.HOVER_CLEARANCE` 0.07 m |
| grip, verify | fingers close, magnet on; verify the object is magnetic, no wider than the fingers and still inside the window: the magnet holds | |
| carry, release | the object rides at the window's centre; a second G puts it down there, on the surface below | release time = `arm.script_seconds()` |

## What is measured, what is assumed

- **Measured (STACK):** the window, the lateral limit, the four target diameters, the
  camera, the first-detection distance.
- **Derived (MODEL):** the reach band 0.099–0.128 m from the arm's IK; the standoff.
- **ASSUMPTION:** the magnet binds 30 mm below any object's top, as on the Stack's
  targets; the camera detects every object type out to the distance at which the
  thinnest target was first seen; a robot-sized line from the pre-grasp pose to the
  window that is free on the plan map is drivable.
- **SIMPLIFIED:** no contact during the reach (the arm moves through nothing), no
  physics on the object, occlusion is 2D (any solid between camera and object hides it).

## Scenarios and golden traces

`coco_lab/test/fixtures/m6f/grasp_scenarios.json` (13 on the Depot: each refusal reason,
picks on the floor, in an aisle and on the mezzanine deck, a release, the person taking
over, STOP, nothing in range, and a hash-v2 run); `grasp_golden.json` beside it pins
their stage logs and state-hash chains (`tools/m6/make_grasp_golden.py`). Every pick
ends inside the Stack's approach window (tested).
