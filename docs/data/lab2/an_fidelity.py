# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Sketch fidelity against Gazebo, from ``lab2_run.sh fidelity`` sessions.

No ROS: reads the sessions' JSON lines and runs coco_lab's Sketch.

**Range error at identical poses.** For every recorded scan, Sketch casts
COCO's full 480-beam LiDAR (``sketch.COCO_LIDAR``) on the saved Nav2 map
at its native 0.05 m from the TRUE pose Gazebo reported at that scan's
stamp. Per beam, ``e = gazebo - sketch``. Beams are classed:

- ``both``: both returned; ``e`` is the range error;
- ``gz_only`` / ``sketch_only``: one returned, the other did not;
- ``neither``.

``both`` is further split by what Sketch's ray hit: an OCCUPIED cell (a
wall or box in the map) or an UNKNOWN cell (the bays, which the saved map
leaves unknown and Gazebo fills with ramps and platforms). A scan whose
robot settled tilted by more than ``--max-tilt`` degrees is excluded and
counted: its LiDAR plane is not the map's.

**Odometry drift.** For every scripted drive, Gazebo's wheel odometry is
placed in the map by the drive's first truth pose, and its error against
the truth is reported at the end and as a maximum, with the distance and
rotation driven. Sketch replays the drive's own recorded command
sequence: with zero noise its odometry IS its truth (wheels never slip),
and with the default ``Noise`` alphas the final drift is a distribution
over ``--seeds`` seeds. Also reported: how far Gazebo's TRUE path departs
from the commanded unicycle (Sketch's truth), i.e. what the commands did.

Usage::

    python3 docs/data/lab2/an_fidelity.py SESSION_DIR... --out F.json
"""

import argparse
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))

from coco_lab import maps, sketch  # noqa: E402
from coco_lab.maps import OCCUPIED, UNKNOWN  # noqa: E402

NAV_YAML = os.path.join(REPO, 'gazebo_models', 'maps', 'coco_navigation.yaml')
INF = float('inf')


def pct(values, q):
    """Nearest-rank percentile (q in [0, 100]) of a non-empty list."""
    s = sorted(values)
    k = max(0, min(len(s) - 1, math.ceil(q / 100.0 * len(s)) - 1))
    return s[k]


def dist_summary(values):
    """Count, mean, sd and the percentiles the docs quote."""
    if not values:
        return {'n': 0}
    return {'n': len(values), 'mean': statistics.fmean(values),
            'sd': statistics.pstdev(values) if len(values) > 1 else 0.0,
            'min': min(values), 'p05': pct(values, 5), 'p25': pct(values, 25),
            'median': pct(values, 50), 'p75': pct(values, 75),
            'p95': pct(values, 95), 'p99': pct(values, 99),
            'max': max(values)}


def hit_class(smap, lab_map, pose, angle, rng):
    """What Sketch's ray hit: 'occupied', 'unknown', 'edge' or None."""
    x, y, th = pose
    mx, my, _ = sketch.COCO_LIDAR.mount
    c, s = math.cos(th), math.sin(th)
    sx, sy = x + c * mx - s * my, y + s * mx + c * my
    if rng == INF:
        return None
    a = th + angle
    # step 1 mm past the entry face into the cell that stopped the ray
    ex = sx + (rng + 1e-3) * math.cos(a)
    ey = sy + (rng + 1e-3) * math.sin(a)
    cell = lab_map.cell_at(ex, ey)
    if cell is None:
        return 'edge'
    v = lab_map.at(cell)
    return {OCCUPIED: 'occupied', UNKNOWN: 'unknown'}.get(v, 'free?')


def analyse_scans(sessions, max_tilt_deg):
    lab_map = maps.load_nav2(NAV_YAML)
    smap = sketch.SketchMap(lab_map)
    angles = sketch.COCO_LIDAR.angles()
    classes = {'both': 0, 'gz_only': 0, 'sketch_only': 0, 'neither': 0}
    err = {'all': [], 'occupied': [], 'unknown': [], 'edge': []}
    per_pose = []
    excluded = []
    hist_edges = [x / 100.0 for x in range(-50, 51, 2)]
    n_scans = 0
    for sess in sessions:
        path = os.path.join(sess, 'scans.jsonl')
        if not os.path.exists(path):
            continue
        for line in open(path):
            r = json.loads(line)
            n_scans += 1
            _, x, y, yaw, z, tilt = r['truth']
            if math.degrees(tilt) > max_tilt_deg:
                excluded.append({'session': os.path.basename(sess),
                                 'i': r['i'], 'k': r['k'],
                                 'tilt_deg': math.degrees(tilt),
                                 'pose': [x, y, yaw]})
                continue
            assert len(r['ranges']) == 480
            assert abs(r['angle_min'] - sketch.COCO_LIDAR.angle_min) < 1e-6
            pose = (x, y, yaw)
            sk = smap.scan(pose, sketch.COCO_LIDAR, angles)
            pe = []
            for i, (g, s) in enumerate(zip(r['ranges'], sk)):
                g = INF if g is None else g
                s = INF if (s < sketch.COCO_LIDAR.range_min
                            or s > sketch.COCO_LIDAR.range_max) else s
                if g < INF and s < INF:
                    classes['both'] += 1
                    e = g - s
                    err['all'].append(e)
                    pe.append(abs(e))
                    hc = hit_class(smap, lab_map, pose, angles[i], s)
                    err.setdefault(hc, []).append(e)
                elif g < INF:
                    classes['gz_only'] += 1
                elif s < INF:
                    classes['sketch_only'] += 1
                else:
                    classes['neither'] += 1
            per_pose.append({'session': os.path.basename(sess), 'i': r['i'],
                             'k': r['k'], 'pose': [x, y, yaw],
                             'median_abs_e': pct(pe, 50) if pe else None,
                             'p90_abs_e': pct(pe, 90) if pe else None})
    a = err['all']
    absd = [abs(v) for v in a]
    hist = [0] * (len(hist_edges) - 1)
    under = over = 0
    for v in a:
        if v < hist_edges[0]:
            under += 1
        elif v >= hist_edges[-1]:
            over += 1
        else:
            hist[min(len(hist) - 1,
                     int((v - hist_edges[0]) / 0.02 + 1e-9))] += 1
    total_beams = sum(classes.values())
    return {
        'scans_recorded': n_scans,
        'scans_used': n_scans - len(excluded),
        'scans_excluded_tilt': excluded,
        'max_tilt_deg': max_tilt_deg,
        'beams': total_beams, 'classes': classes,
        'error_m': {k: dist_summary(v) for k, v in err.items()},
        'abs_error_m': dist_summary(absd),
        'frac_abs_below': {f'{t:.2f}': sum(1 for v in absd if v < t) / len(absd)
                           for t in (0.01, 0.02, 0.05, 0.10, 0.25)},
        'histogram': {'edges_m': hist_edges, 'counts': hist,
                      'below': under, 'above': over},
        'per_pose_worst': sorted([p for p in per_pose if p['p90_abs_e']],
                                 key=lambda p: -p['p90_abs_e'])[:8],
    }


# -- odometry ---------------------------------------------------------------

def compose(a, b):
    """Pose a, then relative pose b."""
    c, s = math.cos(a[2]), math.sin(a[2])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1],
            sketch.wrap(a[2] + b[2]))


def inverse(a):
    c, s = math.cos(a[2]), math.sin(a[2])
    return (-c * a[0] - s * a[1], s * a[0] - c * a[1], -a[2])


def sketch_replay(start, cmds, dts, alphas, seed):
    """Sketch's truth and odometry for a recorded command sequence."""
    import random
    master = random.Random(seed)
    rng = random.Random(master.getrandbits(64))
    pose = start
    odom = (0.0, 0.0, 0.0)
    for (v, w), dt in zip(cmds, dts):
        new = sketch.step_pose(pose, v, w, dt)
        r1, t, r2 = sketch.odom_delta(pose, new)
        n = sketch.sample_delta(r1, t, r2, alphas, rng)
        odom = sketch.apply_delta(odom, *n)
        pose = new
    # odometry placed in the map by the start pose
    return pose, compose(start, odom)


def analyse_drives(sessions, seeds):
    out = []
    for sess in sessions:
        path = os.path.join(sess, 'drives.jsonl')
        if not os.path.exists(path):
            continue
        rows = [json.loads(line) for line in open(path)]
        for label in dict.fromkeys(r['label'] for r in rows):
            ticks = [r for r in rows if r['label'] == label
                     and r['kind'] == 'drive']
            end = [r for r in rows if r['label'] == label
                   and r['kind'] == 'drive_end']
            if not ticks or not end:
                continue
            end = end[0]
            t0 = ticks[0]
            gt0 = tuple(t0['truth'][1:4])
            od0 = tuple(t0['odom'][1:4])
            place = compose(gt0, inverse(od0))  # odom frame -> map
            dist = rot = 0.0
            max_e = 0.0
            seq = ticks + [end]
            for a, b in zip(seq, seq[1:]):
                dist += math.hypot(b['truth'][1] - a['truth'][1],
                                   b['truth'][2] - a['truth'][2])
                rot += abs(sketch.wrap(b['truth'][3] - a['truth'][3]))
            for r in seq:
                o = compose(place, tuple(r['odom'][1:4]))
                max_e = max(max_e, math.hypot(o[0] - r['truth'][1],
                                              o[1] - r['truth'][2]))
            gt_end = tuple(end['truth'][1:4])
            od_end = compose(place, tuple(end['odom'][1:4]))
            gz_pos = math.hypot(od_end[0] - gt_end[0], od_end[1] - gt_end[1])
            gz_yaw = abs(sketch.wrap(od_end[2] - gt_end[2]))
            # Sketch: replay the commands Gazebo was sent, tick for tick
            cmds = [tuple(r['cmd']) for r in ticks]
            dts = [b['t'] - a['t'] for a, b in zip(ticks, ticks[1:])]
            dts.append(0.1)
            sk_truth, sk_odom0 = sketch_replay(gt0, cmds, dts,
                                               (0, 0, 0, 0), 0)
            cmd_vs_gz = math.hypot(sk_truth[0] - gt_end[0],
                                   sk_truth[1] - gt_end[1])
            alphas = sketch.Noise().odom_alphas
            sk_pos, sk_yaw = [], []
            for seed in range(seeds):
                tr, od = sketch_replay(gt0, cmds, dts, alphas, seed)
                sk_pos.append(math.hypot(od[0] - tr[0], od[1] - tr[1]))
                sk_yaw.append(abs(sketch.wrap(od[2] - tr[2])))
            out.append({
                'session': os.path.basename(sess), 'drive': label,
                'status': end['status'], 'ticks': len(ticks),
                'distance_m': dist, 'rotation_rad': rot,
                'sim_s': end['t'] - t0['t'],
                'gazebo': {'final_pos_err_m': gz_pos,
                           'final_yaw_err_rad': gz_yaw,
                           'max_pos_err_m': max_e,
                           'pos_err_per_m': gz_pos / dist if dist else None,
                           'yaw_err_per_rad': gz_yaw / rot if rot >= 1.0
                           else None},
                'gazebo_truth_vs_commanded_unicycle_m': cmd_vs_gz,
                'sketch_zero_noise_final_pos_err_m': math.hypot(
                    sk_odom0[0] - sk_truth[0], sk_odom0[1] - sk_truth[1]),
                'sketch_default_noise': {
                    'alphas': list(alphas), 'seeds': seeds,
                    'final_pos_err_m': dist_summary(sk_pos),
                    'final_yaw_err_rad': dist_summary(sk_yaw)},
            })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('sessions', nargs='+')
    ap.add_argument('--out', required=True)
    ap.add_argument('--max-tilt', type=float, default=2.0)
    ap.add_argument('--seeds', type=int, default=200)
    args = ap.parse_args(argv)
    meta = []
    for s in args.sessions:
        p = os.path.join(s, 'meta.json')
        if os.path.exists(p):
            m = json.load(open(p))
            meta.append({'session': os.path.basename(s),
                         'source_copy_of': m.get('source_copy_of'),
                         'git_commit': m.get('git_commit'),
                         'started_utc': m.get('started_utc'),
                         'runner_checks_failed': m.get('runner_checks_failed'),
                         'void_reason': m.get('void_reason')})
    result = {
        'tool': 'docs/data/lab2/an_fidelity.py',
        'command': 'python3 docs/data/lab2/an_fidelity.py ' + ' '.join(
            os.path.basename(s) for s in args.sessions) +
        f' --max-tilt {args.max_tilt} --seeds {args.seeds}',
        'sessions': meta,
        'map': 'gazebo_models/maps/coco_navigation.yaml (native 0.05 m)',
        'lidar': sketch.COCO_LIDAR.to_dict(),
        'scans': analyse_scans(args.sessions, args.max_tilt),
        'drives': analyse_drives(args.sessions, args.seeds),
    }
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=1, sort_keys=True)
    s = result['scans']
    print('scans used', s['scans_used'], 'of', s['scans_recorded'],
          'beams', s['beams'], s['classes'])
    for k in ('all', 'occupied', 'unknown'):
        d = s['error_m'].get(k, {})
        if d.get('n'):
            print(f"  e[{k}] n={d['n']} median={d['median']:+.4f} "
                  f"p05={d['p05']:+.4f} p95={d['p95']:+.4f}")
    ab = s['abs_error_m']
    print('  |e| median %.4f p95 %.4f p99 %.4f max %.3f' % (
        ab['median'], ab['p95'], ab['p99'], ab['max']))
    for d in result['drives']:
        print(f"  drive {d['session']}/{d['drive']}: {d['distance_m']:.1f} m "
              f"{d['rotation_rad']:.1f} rad; gz odom final "
              f"{d['gazebo']['final_pos_err_m']:.3f} m "
              f"{d['gazebo']['final_yaw_err_rad']:.3f} rad; sketch median "
              f"{d['sketch_default_noise']['final_pos_err_m']['median']:.3f} m")
    return 0


if __name__ == '__main__':
    sys.exit(main())
