# M5 local demo script · target 75 seconds

Draft, not an announcement. Record the actual app; narration must preserve MODEL
and STACK labels and unresolved caveats. No performance number is spoken. Record
on balanced/AC and retain conditions, browser and renderer with the local file.

| Time | Actual screen/action | Narration |
| --- | --- | --- |
| 00–07 | Title: COCO idles under the work light; point to the three cards. | “See what the robot computes. Play, Compare, Research.” |
| 07–14 | Open Play, show existing game cards, enter Free roam. Skip tutorial for this prepared demo. | “Drive the model, take a challenge, or race the planner's ghost.” |
| 14–29 | Drive, stop, click a reachable goal. Press X through scan and planner overlays. Keep MODEL badge visible. | “The scan is what the model sees. These cells show the planner's work. This is kinematics, not a physics simulation.” |
| 29–49 | Open Compare: A* and Dijkstra on the same goal. Reveal the difference view, scrub the shared timeline, show results. | “The same map, goal and seed. Compare the cells each algorithm expanded, the paths and the measured results.” |
| 49–60 | Show the layered costmap and open a cited tour. | “Inspect the costs behind a decision. Every historical claim links to its evidence; unresolved results stay unresolved.” |
| 60–75 | Open Research, filter failures, search a controller, open a recorded run. Keep STACK badge visible. | “Research keeps every recording, including failures. STACK is the full ROS system recorded in Gazebo. No physical robot exists.” |

Local recording, if produced, lives under data/m5/launch/demo/ with conditions JSON.
It is a review artifact, not uploaded or published. A local recording can omit narration;
this script is the voice-over text for Gautham to review. Do not imply the model trace
is the historical Stack run, or that the demo establishes a performance benchmark.
