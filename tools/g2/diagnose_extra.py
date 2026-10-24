#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.6, step 1c: three more measurements on a recorded Depot run (read only), for DIAGNOSIS.md.

    source /opt/ros/jazzy/setup.bash && tools/g2/diagnose_extra.py RUN_DIR GEN_DIR OUT.json

1. **AMCL's own likelihood** (Nav2's likelihood field, the generated params: 60 beams, sigma_hit
   0.2, z_hit / z_rand 0.5, distances capped at laser_likelihood_max_dist 2.0 m, laser_max_range
   100), every 40th scan: at the truth, at the recorded AMCL pose, and the best offset within
   ±0.6 m and ±0.1 rad of the truth.
2. **Short returns**: every scan's returns under 0.6 m, by bearing (10 deg) and range (0.1 m); and
   on open floor only (COCO > 1 m from any mapped obstacle), where only COCO itself or an
   unmapped body could be that close.
3. **Stamp offset**: for scans taken while turning (|w| > 0.3 rad/s), the fraction of beam ends
   within 0.1 m of the map with the truth taken at the scan's stamp + delta.
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diagnose_m6f8 as d  # noqa: E402

ZH, ZR, SIG, MAXD, RMAX = 0.5, 0.5, 0.2, 2.0, 100.0


def amcl_score(mp, scan, pose, step=8):
    x, y, th = pose
    lx, ly = x - 0.09 * math.cos(th) - 0.1 * math.sin(th), y - 0.09 * math.sin(th) + 0.1 * math.cos(th)
    r = np.array(scan.ranges, float)
    a = scan.angle_min + np.arange(len(r)) * scan.angle_increment + th
    idx = np.arange(0, len(r), step)
    r, a = r[idx], a[idx]
    ok = np.isfinite(r) & (r < RMAX) & (r >= scan.range_min)
    dd = d.dist_at(mp, lx + r[ok] * np.cos(a[ok]), ly + r[ok] * np.sin(a[ok]))
    dd = np.where(np.isfinite(dd), np.minimum(dd, MAXD), MAXD)
    return float(np.sum((ZH * np.exp(-dd * dd / (2 * SIG * SIG)) + ZR / RMAX) ** 3))


def main() -> int:
    run, gen, out = sys.argv[1:4]
    data = d.read(os.path.join(run, 'bag'))
    mp = d.load_map(gen)
    truth = (np.array([t for t, _ in data['/model/coco/odometry']]), [d.pose2d(m) for _, m in data['/model/coco/odometry']])
    w = [m.twist.twist.angular.z for _, m in data['/model/coco/odometry']]
    amcl = (np.array([t for t, _ in data['/amcl_pose']]), [d.pose2d(m) for _, m in data['/amcl_pose']])
    rep = {'run': os.path.basename(run.rstrip('/')), 'class': 'STACK (recorded Gazebo + Nav2), measured offline'}
    rows = []
    offs = [(dx, dy, dt) for dx in np.arange(-0.6, 0.61, 0.05) for dy in np.arange(-0.6, 0.61, 0.05) for dt in (-0.1, -0.05, 0.0, 0.05, 0.1)]
    for t, s in data['/scan'][::40]:
        if t < 44 or not len(amcl[0]):
            continue
        g, _ = d.nearest(truth, t)
        am, _ = d.nearest(amcl, t)
        best = max(offs, key=lambda o: amcl_score(mp, s, (g[0] + o[0], g[1] + o[1], g[2] + o[2])))
        rows.append({'t': round(t, 1), 'at_truth': round(amcl_score(mp, s, g), 3), 'at_amcl': round(amcl_score(mp, s, am), 3),
                     'best_offset': [round(float(v), 2) for v in best], 'at_best': round(amcl_score(mp, s, (g[0] + best[0], g[1] + best[1], g[2] + best[2])), 3),
                     'amcl_minus_truth': [round(am[0] - g[0], 3), round(am[1] - g[1], 3)]})
    rep['amcl_likelihood'] = {'model': 'likelihood field, 60 beams, sigma 0.2, z_hit 0.5, z_rand 0.5, max dist 2.0, max range 100', 'rows': rows}
    hist, n = {}, 0
    for t, s in data['/scan']:
        if t < 44:
            continue
        n += 1
        r = np.array(s.ranges)
        a = s.angle_min + np.arange(len(r)) * s.angle_increment
        ok = np.isfinite(r) & (r < 0.6)
        for rr, aa in zip(r[ok], a[ok]):
            k = f'{round(math.degrees(aa) / 10) * 10:+d} deg, {round(rr, 1):.1f} m'
            hist[k] = hist.get(k, 0) + 1
    rep['short_returns'] = {'scans': n, 'per_scan': round(sum(hist.values()) / max(1, n), 2),
                            'bins': {k: round(v / n, 2) for k, v in sorted(hist.items(), key=lambda kv: -kv[1])}}
    # the same, only where COCO stands more than 1 m from any mapped obstacle: what is that close
    # there can only be COCO itself or an unmapped body (G2.6: the first count above was neither)
    n_open, short_open = 0, 0
    for t, s in data['/scan']:
        g, dt = d.nearest(truth, t)
        if dt > 0.05:
            continue
        clear = d.dist_at(mp, np.array([g[0]]), np.array([g[1]]))[0]
        if not (np.isfinite(clear) and clear > 1.0):
            continue
        r = np.array(s.ranges)
        n_open += 1
        short_open += int((np.isfinite(r) & (r < 0.65)).sum())
    rep['short_returns_open_floor'] = {'scans': n_open, 'returns_under_0_65m_per_scan': round(short_open / max(1, n_open), 3)}
    turning = [(t, s) for t, s in data['/scan'] if t >= 44 and abs(w[min(int(np.searchsorted(truth[0], t)), len(w) - 1)]) > 0.3]
    rep['stamp_offset'] = {'turning_scans': len(turning), 'fraction_within_0_1m': {
        f'{dt:+.2f}': round(float(np.mean([d.score(mp, s, d.nearest(truth, t + dt)[0])[1] for t, s in turning[::2]])), 3)
        for dt in (-0.3, -0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2, 0.3)} if turning else None}
    with open(out, 'w') as f:
        json.dump(rep, f, indent=1)
    print(json.dumps({'run': rep['run'], 'short_per_scan': rep['short_returns']['per_scan'], 'open_floor': rep['short_returns_open_floor'], 'stamp': rep['stamp_offset']['fraction_within_0_1m'],
                      'likelihood_best': [r['best_offset'] for r in rows[:6]]}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
