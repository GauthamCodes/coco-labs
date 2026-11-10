"""
Builder exercise: write particle-filter resampling. (Reference solution: low variance.)

Step through the cumulative weights at r, r + 1/N, r + 2/N, ... with r = rng.random() / N
(exactly coco_lab.localise.low_variance_resample):
one random number, and each particle gets floor(N w) or ceil(N w) copies.
"""


def resample(particles, weights, rng):
    """Return len(particles) copies chosen in proportion to weights."""
    n = len(particles)
    step = 1.0 / n
    target = rng.random() * step      # one random point in [0, 1/N)
    c = weights[0]
    i = 0
    out = []
    for _ in range(n):
        while target > c and i < n - 1:
            i += 1
            c += weights[i]
        out.append(particles[i])
        target += step
    return out
