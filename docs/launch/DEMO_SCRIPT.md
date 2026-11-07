# 90-second demo — shot list and script (draft; recording and publishing are Gautham's)

Format: screen capture of the live site (desktop, 1920×1080, dark theme), voice-over, no music
under speech. Every on-screen number must be readable on the page shown at that moment (nothing
added in editing). Labels MODEL / STACK stay visible in every shot.

| # | Time | Shot (what is on screen) | Voice-over |
| --- | --- | --- | --- |
| 1 | 0:00–0:08 | Title screen; click **Play** | "This is COCO, a ROS 2 robot — modelled in your browser. No install." |
| 2 | 0:08–0:20 | Fetch Rush round: drive to an order, the route ghost and LiDAR visible; the MODEL · kinematic badge | "The game is the front door. Underneath is a deterministic robot model: every tick is hashed." |
| 3 | 0:20–0:30 | Toggle **SIM** view: costmap, scan, the planner's expansions | "Switch to SIM and you see what the robot computes — costmaps, plans, decisions." |
| 4 | 0:30–0:42 | **Workbench → Experiments**: run a small A* vs D* Lite experiment; results with Wilson intervals | "Workbench turns that into science: experiments with honest statistics, shared as links that reproduce exactly in any browser." |
| 5 | 0:42–0:55 | **Algorithm Studio**: open the A* starter, edit the heuristic, Run; expansions stream in | "Bring your own algorithm: write a planner in Python against ROS 2-shaped messages and watch it think." |
| 6 | 0:55–1:08 | **Export ROS 2**; cut to a recorded Gazebo + Nav2 run of the same file (STACK label on screen) | "Export the same file as a ROS 2 node, and it runs in Gazebo with Nav2 — the browser result and the real stack side by side." |
| 7 | 1:08–1:20 | **Leaderboard**: the Lazy Theta* entry — MODEL row beside its STACK row (0/5 drives) | "Submissions are verified in a sandbox on public and held-out scenarios — and the negative results stay visible: this planner wins in the model and fails every drive under Nav2's controller." |
| 8 | 1:20–1:30 | About → **Cite**; the repository README | "COCO-Bench is open source, citable, and every number in the paper regenerates from the repository. Try it — the link is below." |

Captions: on for every line. End card: live URL, repository URL, "MODEL = browser model · STACK =
ROS 2 in Gazebo (simulation) · no physical robot".
