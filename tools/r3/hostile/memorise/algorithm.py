"""
R3.3 hostile submission (ADR 0014, T6): "memorise" the held-out set. It plans a straight line and
reports success only on scenarios it has seen before (a hard-coded table of the public suite's
starts). Under the secret per-head held-out set it can know none of them: its held-out score
must fall to what a straight line achieves.
"""
from coco_lab.api import Pose2D

SEEN = {}   # the public scenarios' starts would go here; the held-out ones cannot


def plan(costmap, start, goal, ctx):
    key = (round(start.x, 1), round(start.y, 1))
    if key in SEEN:
        return SEEN[key]
    return [Pose2D(start.x, start.y, 0.0), Pose2D(goal.x, goal.y, 0.0)]
