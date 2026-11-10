# R4.7 wrong solution for m6-logodds: clamps once at the end
"""
Builder exercise: update an occupancy cell in log-odds. (Reference solution.)

Each hit adds L_OCC, each pass adds L_FREE; clamp to [L_MIN, L_MAX] after every step.
These are COCO's mapping constants (coco_lab.occgrid.GridParams).
"""
L_OCC = 0.85
L_FREE = -0.4
L_MIN = -4.0
L_MAX = 4.0


def update(l, hits):
    """The cell's log-odds after the observations in hits (True = hit, False = passed)."""
    for hit in hits:
        l += L_OCC if hit else L_FREE
    return max(L_MIN, min(L_MAX, l))
