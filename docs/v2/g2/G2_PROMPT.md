# G2 · Sim Identity — the prompt (Gautham, 2026-10-23)

Saved verbatim as §0 asks. Planning answers given on 2026-10-24 are in [G2_STATUS.md](G2_STATUS.md).

---

You are building G2 · Sim Identity for COCO Lab. G1 made Play look like a mobile game, and Gautham is happy with that direction. Now he wants the game to look and feel like it comes from robotics simulators (Gazebo, RViz, Isaac Sim) and to make its ROS 2 origin and purpose prominent, while staying attractive and easy to play.

The idea: a game that is visibly a robotics stack underneath. The player should always see that a real robot's software is at work (topics, frames, sensors, plans, sim time), and one tap should turn the game view into a proper RViz-style view of the same moment. Read docs/v2/g1/G1_REVIEW.md first; its "robotics resemblance" proposals are the starting point.

0. Setup and rules
Branch. git fetch origin, then create a worktree at ~/coco_labs_ws/worktrees/g2 on branch v2/g2-sim-identity from origin/main.
If #27 isn't merged yet, branch from origin/claude/serene-davinci-v9y796 instead and say so.
Paperwork.
Save this prompt as docs/v2/g2/G2_PROMPT.md.
Keep progress in docs/v2/g2/G2_STATUS.md.
Add a dated (2026-10-23) entry to docs/STATUS.md's plan-change log, and add G2 to README §7, before the M6 UI phase.
Commit [G2.n] at each checkpoint and push.
All the G1 rules still hold. In particular:
The truth:
Rendering never changes the model.
Game rules are not physics.
Hashes are versioned.
Evidence labels are truthful.
Never merge, deploy or release.
No destructive git commands.
Never invent numbers.
Machine and phone:
Balanced profile on AC; one simulator at a time; never Gazebo --fast.
Put the phone's saved settings back when you finish with it.
Black out the status bar on every phone screenshot before it is committed.
Honesty about ROS (this is critical). The browser runs a ROS 2-shaped Python model, not ROS 2. Every ROS-looking element must say which one it is:
Model: topic names, frames and message shapes mirror COCO's real stack and are labelled "model". For example, the ROS graph panel is titled "ROS 2 graph (model of COCO's stack)".
Real ROS 2: recorded from Gazebo + Nav2 and labelled STACK.
Never write "running ROS 2" about the browser.
Use the words ROS 2, Gazebo, RViz, Nav2 and MoveIt as plain-text references, never their logos. "Isaac Sim-inspired" may describe the lighting, never claim compatibility.
Phone first. Everything must hold 60 fps on the real Nothing Phone (1) at the default tier, and a full-screen panel can never cover STOP.
1. Gautham's decisions on G1.13's open items (record them in G2_STATUS and STATUS, dated 2026-10-23)
Phone round variety. Fetch Rush routes may cross a forklift lane only at a marked crossing (hazard-striped), never run along a lane. Then choose the smallest budget giving at least 3 distinct rounds with timers ≤ 5:00, or ≤ 6:00 if 5:00 is impossible.
The AUTO stall of 119–141 ms against a 100 ms target is accepted for now and tracked as an open item. Do not spend G2 time on it unless a G2 change makes it worse.
Heavy saved settings on phones. Never override the player's settings silently. If fps stays under 55 for 10 s, show a one-tap "Switch to recommended settings" toast.
The old phone screenshots in git history (status bar icons only) are accepted; no history rewrite.
2. The design
2.1 Two views of the same moment: GAME and SIM

Replace the small eye icon with a clear GAME | SIM segmented switch at the top right (the V key on desktop). Switching is instant, keeps the run going, and never changes the model.

GAME view is G1's look, plus permanent robotics cues that are always visible and subtle:
LiDAR rays and hit points, faintly
the robot's footprint outline
small TF axes on the robot
the global plan as a thin line
The player should always see the robot sensing and planning.
SIM view is RViz-style:
a dark neutral background and a metric floor grid (1 m major, 0.1 m minor) with axis colours
world geometry flat-shaded and semi-transparent, as in Gazebo's wireframe or transparent modes
TF frames with labels: map, odom, base_footprint, lidar_link, and the arm frames
LaserScan as coloured points by range
costmaps (global and local) in RViz's costmap palette
/plan and the local trajectory candidates, plus the chosen one
the footprint polygon and the goal pose arrow
the localisation particle cloud, if the model has one; otherwise its covariance ellipse
an RViz-like orbit camera
The HUD shrinks to STOP, joystick, primary action and the switch, and all of it still works.
2.2 Telemetry, everywhere
A telemetry strip under the speed gauge, monospace and always visible: /cmd_vel v 0.24 ω −0.10 · /odom x 3.21 y −1.04 θ 92° · sim 67.6 s. Use real model values and topic names from the M6F.7 ROS shapes.
A Gazebo-style bottom bar, desktop and SIM view only: Sim time · Real time · RTF · Iterations, all real values.
A /rosout-style console, collapsible, bottom-left. Model events are written as ROS log lines with node names from the M6F.7 ROS graph, for example [INFO] [planner_server]: path found, 12.16 m, 22,319 expansions and [WARN] [controller_server]: obstacle 0.32 m ahead. Only real model events. On phones it shows the last line only, and tapping it expands it.
2.3 Panels (desktop docked like RViz or Foxglove; phone as a bottom sheet that never covers STOP)
Displays: an RViz-style checkbox tree (Grid, RobotModel, TF, LaserScan, Map, Global Costmap, Local Costmap, Global Plan, Local Plan, Footprint, Goal), with per-display options such as colour, point size and alpha. Saved in prefs.
ROS 2 graph (model of COCO's stack): nodes and topics, live rates and the last message time. /scan → … → /cmd_vel lights up as messages flow. Tapping a topic opens Topic echo.
Topic echo: live fields of the chosen message in ROS YAML style (LaserScan, Odometry, Twist, Path, OccupancyGrid metadata, TF).
Plot: rqt_plot-style plots of v, ω, distance to goal and min obstacle distance over time.
Learn links: each panel has a "?" that opens a one-paragraph explanation of the ROS 2 concept and its real-world counterpart in COCO's stack.
2.4 ROS 2 output you can actually use
Export as a rosbag2 file. The results screen and the pause menu get "Save as rosbag2 (MCAP)". It writes the run's model messages with ROS 2 message schemas and correct timestamps and frames into an MCAP file that ros2 bag info and ros2 bag play accept and Foxglove opens.
Prove it on the laptop:
ros2 bag info on an exported file
ros2 bag play it while RViz shows the scan, TF, map and plan
commit screenshots and logs
It is labelled MODEL inside the bag (a metadata field).
Race Nav2. Once a real Gazebo + Nav2 ghost of a phone round exists (checkpoint G2.6), Play offers "Race Nav2 (real ROS 2 recording)": a translucent ghost of COCO driven by the recording, labelled STACK. The results screen then compares your run, the browser model's planner, and real Nav2 in Gazebo.
2.5 Simulator-grade looks (still a game)
Lighting and materials closer to Isaac Sim:
physically based materials with a baked environment map for reflections on the polished floor
SSAO on the high tier only
consistent metal, plastic and rubber on COCO, with real wheel and joint motion from the model (wheels spin with odometry, and the arm joints follow the model's joint states)
On the title screen: "COCO Lab · a ROS 2 robot you can drive in your browser", with a short line of truthful badges: Model of COCO's ROS 2 stack · Nav2 · Gazebo Harmonic · MoveIt. The ⓘ explains what is model and what is recorded.
Results screen: a small "what the planner computed" replay inset (expansions or plan), and a link to the matching Gazebo recording when one exists.
3. Checkpoints (in this order)
G2.0 Baseline
Set up as in §0, build, and run all suites.
Capture before screenshots: desktop, emulated phone, and the real phone (status bar blacked out).
G2.1 Decisions

Apply the four decisions in §1, with tests, and regenerate the Fetch Rush references.

G2.2 GAME | SIM switch and SIM view

Build the SIM view, the always-on cues in GAME view, and the TF frames. On the real phone, SIM view must hold 60 fps with every display on, or drop to a documented lighter default.

G2.3 Telemetry

The telemetry strip, the Gazebo bottom bar and the /rosout console, all from real model values.

G2.4 Panels

Displays, the ROS 2 graph, Topic echo, Plot and the Learn links, on desktop and on the phone.

G2.5 rosbag2 export

Build the export, then prove it with ros2 bag info and ros2 bag play plus RViz, on the laptop.

G2.6 Real ROS 2 ghost
Fix Gazebo + Nav2 on the Depot. Nav2 fails on the Dock 1 route, and localisation drifts about 0.5 m.
Find the cause first: map resolution or origin mismatch, inflation versus aisle width, AMCL parameters, a missing scan-matching feature in a featureless area, or the generated SDF's collision geometry.
Fix whatever is wrong in the generated files or params, never in the reference copies.
Record real ghosts. Once Nav2 is reliable (at least 5 of 5 runs succeed), record real Nav2 ghosts for the phone rounds and convert them.
Wire up Race Nav2, and add the three-way comparison to the results screen.
G2.7 Looks

Isaac-like materials and lighting, wheel and arm motion, the new title, and the results inset. Check budgets on the real phone.

G2.8 Close
Capture after screenshots for everything in G2.0, and write docs/v2/g2/BEFORE_AFTER.md.
Run all suites, determinism (v1, v2, v3) and the real-phone check (10 minutes in GAME view and 2 minutes in SIM view, fps and heat).
Write G2_RESULTS.md, push, and open a PR into main titled "G2 · Sim Identity", ready for review. Don't merge.
4. Stop and report if
Any model or golden hash changes.
Something would need a ROS/Gazebo/RViz/NVIDIA logo or non-free asset.
A UI element would claim the browser runs ROS 2.
The phone can't hold 60 fps in GAME view after two optimization passes.
5. Final report
Checkpoints done (G2.x):
Branch, SHAs, pushed, clean:
Decisions applied (phone rounds: budget, rounds, timers):
GAME/SIM: what's shown, phone fps per view
Telemetry, console, panels: done / notes
rosbag2 export: ros2 bag info / play / RViz result (evidence)
Gazebo + Nav2: cause of the Dock 1 failure and the drift, fix, success rate, ghosts recorded (checksums)
Looks: before/after, budgets
Tests and determinism:
Real phone: fps, heat, settings restored
Questions for Gautham:
Next step:
