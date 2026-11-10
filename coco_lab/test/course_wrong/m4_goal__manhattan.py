# R4.7 wrong solution for m4-goal: Manhattan distance instead of Euclidean
"""
Builder exercise: add a goal tolerance. (Reference solution.)

Nav2's goal checker says the goal is reached when BOTH hold:

  - the distance to the goal is at most xy_tolerance (Nav2 compares squared distances:
    dx*dx + dy*dy <= xy_tolerance**2)
  - the heading differs from the goal's by at most yaw_tolerance, measured the SHORT way
    round (3.1 rad and -3.1 rad are only about 0.08 rad apart)
"""
import math


def angle_diff(a, b):
    """a - b, wrapped into [-pi, pi]."""
    return math.atan2(math.sin(a - b), math.cos(a - b))


def goal_reached(pose, goal, xy_tolerance, yaw_tolerance):
    """pose and goal are [x, y, theta] (metres, radians); True when within both tolerances."""
    dx, dy = pose[0] - goal[0], pose[1] - goal[1]
    if abs(dx) + abs(dy) > xy_tolerance:
        return False
    return abs(angle_diff(pose[2], goal[2])) <= yaw_tolerance
