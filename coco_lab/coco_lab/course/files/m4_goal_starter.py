"""
Builder exercise: add a goal tolerance.

A real robot never stops exactly on the goal; a controller has to decide "close enough".
Nav2's goal checker says the goal is reached when BOTH hold:

  - the distance to the goal is at most xy_tolerance (Nav2 compares squared distances:
    dx*dx + dy*dy <= xy_tolerance**2)
  - the heading differs from the goal's by at most yaw_tolerance, measured the SHORT way
    round (3.1 rad and -3.1 rad are only about 0.08 rad apart)

Both of Nav2's defaults are 0.25 (metres and radians). Write goal_reached(); the page calls it
with many poses, some exactly on the boundary and some across the +pi/-pi wrap.
"""
import math


def angle_diff(a, b):
    """a - b, wrapped into [-pi, pi]."""
    return math.atan2(math.sin(a - b), math.cos(a - b))


def goal_reached(pose, goal, xy_tolerance, yaw_tolerance):
    """pose and goal are [x, y, theta] (metres, radians); True when within both tolerances."""
    # TODO: the position test and the heading test (angle_diff is ready for you)
    return False
