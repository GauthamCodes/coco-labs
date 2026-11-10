"""
Builder exercise: update an occupancy cell in log-odds.

An occupancy grid stores, for each cell, the log-odds that it is occupied:
l = log(p / (1 - p)). 0 means "no idea" (p = 0.5). Each time a LiDAR beam ENDS in the cell,
add L_OCC; each time a beam passes THROUGH it, add L_FREE (negative). Adding is Bayes' rule in
log-odds form. Clamp after every step to [L_MIN, L_MAX], so a cell seen as a wall a thousand
times can still be cleared when the wall moves.

Write update(l, hits): start from l, then for each entry of hits (True: the beam ended here;
False: it passed through) add the right amount and clamp. Return the final log-odds.
These are COCO's mapping constants.
"""
L_OCC = 0.85
L_FREE = -0.4
L_MIN = -4.0
L_MAX = 4.0


def update(l, hits):
    """The cell's log-odds after the observations in hits (True = hit, False = passed)."""
    # TODO: add L_OCC or L_FREE for each observation, clamping after each one
    return l
