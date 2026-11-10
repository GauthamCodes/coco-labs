"""
Builder exercise: write particle-filter resampling. (Reference solution: low variance.)

Step through the cumulative weights at r, r + 1/N, r + 2/N, ... with r = rng.random() / N:
one random number, and each particle gets floor(N w) or ceil(N w) copies.
"""


def resample(particles, weights, rng):
    """Return len(particles) copies chosen in proportion to weights."""
    n = len(particles)
    out = []
    r = rng.random() / n
    c = weights[0]
    i = 0
    for k in range(n):
        u = r + k / n
        while u > c and i < n - 1:
            i += 1
            c += weights[i]
        out.append(particles[i])
    return out
