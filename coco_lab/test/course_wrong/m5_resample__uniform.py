# R4.7 wrong solution for m5-resample: picks particles uniformly, ignoring the weights
"""
Builder exercise: write particle-filter resampling. (Reference solution: low variance.)

Step through the cumulative weights at r, r + 1/N, r + 2/N, ... with r = rng.random() / N
(exactly coco_lab.localise.low_variance_resample):
one random number, and each particle gets floor(N w) or ceil(N w) copies.
"""


def resample(particles, weights, rng):
    """Return len(particles) copies chosen in proportion to weights."""
    n = len(particles)
    return [particles[int(rng.random() * n)] for _ in range(n)]
