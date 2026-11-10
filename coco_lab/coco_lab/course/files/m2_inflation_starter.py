"""
Builder exercise: write Nav2's inflation cost.

Nav2's inflation layer gives every cell near an obstacle a cost from its distance d (metres)
to the nearest obstacle cell, so planners prefer to keep away from walls:

  d == 0                         254  lethal: the obstacle itself
  0 < d <= robot radius          253  inscribed: the robot's centre here means a collision
  robot radius < d <= inflation  252 * exp(-cost_scaling_factor * (d - robot radius)),
                                      truncated to a whole number, as Nav2 stores a byte
  d > inflation radius           0    free

Write inflation_cost() so it returns exactly what Nav2 would. The page calls it with many
distances and compares every value.
"""
import math


def inflation_cost(distance, robot_radius, inflation_radius, cost_scaling_factor):
    """The cost (0..254) of a cell ``distance`` metres from the nearest obstacle."""
    # TODO: the four cases above, in that order
    return 0
