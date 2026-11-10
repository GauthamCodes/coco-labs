"""
Builder exercise: write particle-filter resampling.

A particle filter keeps many guesses (particles) of the robot's pose. After a scan, each
guess gets a weight: how well the scan, cast from that guess, lands on the map's walls.
Resampling makes a new set of the same size by copying guesses in proportion to their
weights: good guesses get several copies, bad ones die out.

Write resample(particles, weights, rng):
  - particles: a list of [x, y, theta]; weights: one number per particle, summing to 1
  - return a NEW list with the same number of particles, each one a copy of an input
  - a particle with weight 0 must never be copied; one with weight w gets about N * w copies
  - use rng.random() (a number in [0, 1)) for randomness: the run must be repeatable

The low-variance ("systematic") method uses ONE random number: step through the cumulative
weights at r, r + 1/N, r + 2/N, ... with r = rng.random() / N. Any correct method passes.
"""


def resample(particles, weights, rng):
    """Return len(particles) copies chosen in proportion to weights."""
    # TODO: replace this (it keeps every particle once, whatever its weight)
    return list(particles)
