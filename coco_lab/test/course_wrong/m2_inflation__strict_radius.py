# R4.7 wrong solution for m2-inflation: distance == robot radius treated as outside
"""
Builder exercise: write Nav2's inflation cost. (Reference solution.)

Nav2's inflation layer gives every cell near an obstacle a cost from its distance d (metres)
to the nearest obstacle cell, so planners prefer to keep away from walls:

  d == 0                         254  lethal: the obstacle itself
  0 < d <= robot radius          253  inscribed: the robot's centre here means a collision
  robot radius < d <= inflation  252 * exp(-cost_scaling_factor * (d - robot radius)),
                                      truncated to a whole number, as Nav2 stores a byte
  d > inflation radius           0    free
"""
import math


def inflation_cost(distance, robot_radius, inflation_radius, cost_scaling_factor):
    """The cost (0..254) of a cell ``distance`` metres from the nearest obstacle."""
    if distance == 0:
        return 254
    if distance > inflation_radius:
        return 0
    if distance < robot_radius:
        return 253
    return int(252 * math.exp(-cost_scaling_factor * (distance - robot_radius)))
