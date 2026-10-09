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
Fidelity report v1 (M2.9): docs/v2/FIDELITY_v1.md and the "model gap" chips.

Both are RENDERED from committed measurements, never typed:
``docs/v2/data/m2/m29/fidelity_v1.json`` (the Arena against Lab 2's
recorded Gazebo sessions, made by ``arena_fidelity.py``; its tracking rows
are M2.5's) and ``docs/data/lab2/fidelity/fidelity.json`` (Lab 2's split
of the same beams by what the ray hit). ``test_fidelity.py`` fails if the
report is stale; ``build_catalog.py`` writes the chips to
``generated/fidelity.json``.
"""

import json
import os
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
SOURCE = 'docs/v2/data/m2/m29/fidelity_v1.json'
LAB2 = 'docs/data/lab2/fidelity/fidelity.json'
REPORT = os.path.join(REPO, 'docs', 'v2', 'FIDELITY_v1.md')
#: the report's section each chip links to (GitHub anchors of its headings)
ANCHORS = {'lidar': '1-lidar-at-identical-poses', 'odometry': '2-odometry-straight-and-turning',
           'tracking': '3-controller-tracking-against-the-lab-5-recordings'}
GAP_IDS = tuple(ANCHORS)


def load():
    """Return (the Arena's measurement, Lab 2's)."""
    with open(os.path.join(REPO, SOURCE), encoding='utf-8') as f:
        a = json.load(f)
    with open(os.path.join(REPO, LAB2), encoding='utf-8') as f:
        b = json.load(f)
    return a, b


def _m(v, d=3):
    return f'{v:.{d}f}'


def _mm(v):
    return f'{v * 1000:.1f} mm'


def _cm(v):
    return f'{v * 100:.1f} cm'


def _span(s, d=3):
    return f'{_m(s["median"], d)} [{_m(s["p05"], d)}–{_m(s["p95"], d)}]'


def _rng(vals, d=3):
    lo, hi = _m(min(vals), d), _m(max(vals), d)
    return lo if lo == hi else f'{lo}–{hi}'


def _drive(d):
    return f'{d["session"]} {d["drive"]}'


def _turning(a):
    return [d for d in a['drives'] if d['rotation_rad'] >= 1.0]


def gaps(a=None) -> Dict[str, Dict[str, str]]:
    """The chips: id -> title, what the gap is (numbers from the JSON), the report anchor."""
    if a is None:
        a, _ = load()
    s = a['scans']
    ab = s['abs_error_m']
    straight = [d for d in a['drives'] if d['rotation_rad'] < 1.0]
    turning = _turning(a)
    over = [d['yaw_overcount']['gazebo'] for d in turning]
    sk_straight = [d['arena']['slip_off']['default_noise']['final_pos_err_m']['median'] for d in straight]
    # where every controller drove in both worlds (head-on differs by construction; run 15 never moves)
    agree = [r for r in a['tracking']['rows'] if r['scenario'] in ('static_room', 'crossing')]
    means_model = [r['model_tracking_mean_m']['median'] for r in agree if r['model_tracking_mean_m']['n']]
    means_stack = [r['stack_tracking_mean_m']['median'] for r in agree if r['stack_tracking_mean_m']['n']]
    return {
        'lidar': {
            'title': 'LiDAR',
            'text': (f'The model\'s LiDAR is 2D: it sees the bays\' 3D ramps only as footprints. Against Gazebo at the same '
                     f'{s["scans_used"]} poses, {s["classes"]["both"]:,} beams: |error| median {_mm(ab["median"])}, '
                     f'95th percentile {_cm(ab["p95"])}, 99th {_m(ab["p99"], 2)} m.'),
            'anchor': ANCHORS['lidar']},
        'odometry': {
            'title': 'odometry',
            'text': (f'Gazebo\'s wheel odometry was exact on a straight line ({_m(max(d["gazebo"]["final_pos_err_m"] for d in straight))} m '
                     f'over {_m(straight[0]["distance_m"], 1)} m) and over-counted turns {min(over):.2f}–{max(over):.2f}×. '
                     f'The model\'s default noise is direction-blind (median {_rng(sk_straight, 2)} m over '
                     f'the same straight); its wheel-slip option over-counts turns {1 / a["slip_turn"]:.2f}×, a factor fitted on a '
                     f'recorded tour.'),
            'anchor': ANCHORS['odometry']},
        'tracking': {
            'title': 'controllers',
            'text': (f'The model\'s DWA, RPP and MPPI are smaller than Nav2\'s and its people are solid (Gazebo\'s walked through '
                     f'the robot). On the hairpin and the crossing, mean tracking error: model {_rng(means_model)} m, '
                     f'stack {_rng(means_stack)} m.'),
            'anchor': ANCHORS['tracking']},
    }


def report(a=None, b=None) -> str:
    """Render docs/v2/FIDELITY_v1.md."""
    if a is None:
        a, b = load()
    s = a['scans']
    ab, e = s['abs_error_m'], s['error_m']
    ident = s['vs_sketch_on_nav2_map']
    lab2e = b['scans']['error_m']
    L: List[str] = [
        '# Fidelity report v1: the Arena against the Stack',
        '',
        f'GENERATED by `lab_web/tools/fidelity.py` from `{SOURCE}` (made by `docs/v2/data/m2/m29/arena_fidelity.py`) '
        f'and `{LAB2}`; `lab_web/tools/test_fidelity.py` fails if this file is stale. Every number below is read '
        'from those files.',
        '',
        '**Evidence classes.** The model under test is the Arena (`coco_lab.arena`, MODEL), the one in the browser. '
        'The reference is the full ROS 2 stack in Gazebo (STACK): Lab 2\'s two recorded fidelity sessions '
        f'({", ".join(f"`{x}`" for x in a["sessions"])}) and Lab 5\'s recorded drives. No physical robot exists, so '
        'nothing here is a statement about one.',
        '',
        'Inputs held fixed: the same recorded poses, scans and command sequences Lab 2 measured its Sketch on, '
        'Lab 2\'s loaders and statistics (imported unchanged), and M2.5\'s controller runs (re-tabulated, not re-run).',
        '',
        '## 1. LiDAR at identical poses',
        '',
        f'Each recorded scan\'s TRUE pose (tilt at most 2°; {s["scans_used"]} of {s["scans_recorded"]} scans used, '
        f'{len(s["scans_excluded_tilt"])} excluded) is cast by the Arena\'s own ray caster on its world '
        f'(`{a["world"]}`): all 480 beams, no range noise. Per beam, e = Gazebo − Arena.',
        '',
        '| | |',
        '|---|---|',
        f'| beams | {s["beams"]:,}: both returned {s["classes"]["both"]:,}, only Gazebo {s["classes"]["gz_only"]}, '
        f'only the Arena {s["classes"]["arena_only"]}, neither {s["classes"]["neither"]:,} |',
        f'| error e (both returned) | median {_mm(e["median"])}, 5th percentile {_mm(e["p05"])}, 95th {_mm(e["p95"])} |',
        f'| \\|e\\| | median {_mm(ab["median"])}, 95th percentile {_cm(ab["p95"])}, 99th {_m(ab["p99"], 2)} m, '
        f'max {_m(ab["max"], 2)} m |',
        '| beams within 1 / 5 / 10 cm | ' + ' / '.join(f'{100 * s["frac_abs_below"][k]:.1f} %' for k in ('0.01', '0.05', '0.10'))
        + ' |',
        f'| the Arena against Lab 2\'s Sketch on the Nav2 map | {ident["beams_identical"]:,} beams identical, '
        f'{ident["beams_different"]} different |',
        '',
        f'**The Arena\'s world is, to the LiDAR, the Stack\'s saved map**: every one of the {ident["beams_identical"]:,} '
        'beams it casts equals the one Lab 2\'s Sketch cast on the Nav2 map. So its LiDAR gap is exactly the one Lab 2 '
        'measured. Its JSON splits the beams by the cell the ray ended in: '
        f'{lab2e["occupied"]["n"]:,} of {lab2e["all"]["n"]:,} end in an OCCUPIED cell (e median {_mm(lab2e["occupied"]["median"])}, '
        f'5th–95th percentile {_mm(lab2e["occupied"]["p05"])} to {_mm(lab2e["occupied"]["p95"])}), so that split does not '
        'locate the large errors. Lab 2 located them by inspection, as beams meeting the bays\' 3D ramps and platforms, '
        'which a 2D map at scan height cannot hold (docs/labs/LAB2_LOCALISE.md section 4.1); that is its finding, not '
        'something measured again here.',
        '',
        'The five poses where the Arena is worst (90th-percentile |e| over a scan\'s beams; the worst scan of each pose):',
        '',
        '| session | pose # | pose (x, y, yaw) | median \\|e\\| | 90th pct \\|e\\| |',
        '|---|---|---|---|---|',
    ]
    seen = set()
    for p in s['per_pose_worst']:
        if (p['session'], p['i']) in seen or len(seen) == 5:
            continue
        seen.add((p['session'], p['i']))  # several scans per pose: the worst of each
        x, y, th = p['pose']
        L.append(f'| {p["session"]} | {p["i"]} | ({_m(x, 2)}, {_m(y, 2)}, {_m(th, 2)}) | {_mm(p["median_abs_e"])} | '
                 f'{_m(p["p90_abs_e"], 3)} m |')
    L += [
        '',
        '## 2. Odometry, straight and turning',
        '',
        'Each scripted drive\'s recorded command sequence is replayed tick for tick through the Arena\'s motion '
        'functions and its odometry noise (`sample_delta`, the Arena\'s default alphas '
        f'{tuple(a["drives"][0]["arena"]["slip_off"]["default_noise"]["alphas"])}, '
        f'{a["drives"][0]["arena"]["slip_off"]["default_noise"]["seeds"]} seeds), with the wheel-slip option off '
        f'(the default) and on (the body turns {a["slip_turn"]:.4f} of what the wheels report). Gazebo\'s column is its '
        'wheel odometry\'s error against its own ground truth on the same drive. Arena cells: median [5th–95th '
        'percentile] over the seeds; "no noise" is the model with its noise switched off.',
        '',
        '| drive | distance, rotation | Gazebo odometry error | Arena, slip off | Arena, slip on, no noise | Arena, slip on |',
        '|---|---|---|---|---|---|',
    ]
    for d in a['drives']:
        off, on = d['arena']['slip_off'], d['arena']['slip_on']
        L.append(f'| {_drive(d)} | {_m(d["distance_m"], 1)} m, {_m(d["rotation_rad"], 1)} rad | '
                 f'{_m(d["gazebo"]["final_pos_err_m"])} m | {_span(off["default_noise"]["final_pos_err_m"])} m | '
                 f'{_m(on["zero_noise"]["final_pos_err_m"])} m | {_span(on["default_noise"]["final_pos_err_m"])} m |')
    L += [
        '',
        '**In a straight line** Gazebo\'s skid-steer odometry is exact (the slip option changes nothing there); the '
        'Arena\'s default noise drifts anyway, because it is direction-blind. **In turns** Gazebo\'s wheels report more '
        'rotation than the body made. That over-count is what the slip option models:',
        '',
        '| drive | true rotation | wheel odometry\'s rotation | over-count: Gazebo | Arena slip off | Arena slip on |',
        '|---|---|---|---|---|---|',
    ]
    for d in _turning(a):
        o = d['yaw_overcount']
        L.append(f'| {_drive(d)} | {_m(d["rotation_rad"], 1)} rad | {_m(d["wheel_odom_rotation_rad"], 1)} rad | '
                 f'{o["gazebo"]:.3f}× | {o["arena_slip_off"]:.3f}× | {o["arena_slip_on"]:.3f}× |')
    sq = [d for d in _turning(a) if d['drive'] == 'square']
    tours = [d for d in a['drives'] if d['drive'] == 'tour']
    L += [
        '',
        f'**Caveats, each measured here.** The slip factor {a["slip_turn"]:.4f} was FITTED on a recorded Gazebo tour '
        '(`coco_lab/coco_lab/arena.py` `SLIP_TURN`, docs/labs/LAB2_LOCALISE.md section 4.1), so the tour rows with slip '
        'are not an independent test; the square is. A tour\'s final position error depends on where along 120 m the '
        f'heading errors fell: Gazebo\'s two runs of the same tour ended {_m(tours[0]["gazebo"]["final_pos_err_m"], 2)} m '
        f'and {_m(tours[1]["gazebo"]["final_pos_err_m"], 2)} m off, so one run is not a rate.',
        '',
    ]
    if sq:
        d = sq[0]
        L += [
            '**What the same commands did to the body.** Lab 2\'s driver steered on ground truth, so its commands carry '
            'Gazebo\'s own corrections; replayed open loop they mean something over a short drive only. On the square '
            f'({_m(d["distance_m"], 1)} m), the Arena\'s body ended {_m(d["arena"]["slip_off"]["truth_end_vs_gazebo_truth_m"], 2)} m '
            f'from Gazebo\'s with slip off and {_m(d["arena"]["slip_on"]["truth_end_vs_gazebo_truth_m"], 2)} m with slip on. '
            'The 120 m tours are not compared this way: an open-loop replay of a closed-loop drive diverges in any model.',
            '',
        ]
    L += [
        '## 3. Controller tracking against the Lab 5 recordings',
        '',
        f'From `{a["tracking"]["source"]}` (M2.5, docs/v2/M2_MOVE_COMPARISON.md): the same frozen paths, robot and limits; '
        'STACK = Nav2 in Gazebo, 5 runs per cell (3 for run 15); MODEL = the Arena\'s controllers, seeds 1–5. Tracking '
        'error = distance from the path, measured by the same `coco_lab.movemetrics` code. Cells: median [min–max] '
        'over the runs.',
        '',
        '| scenario | controller (stack / model) | outcomes: stack | outcomes: model | mean tracking error: stack | model |',
        '|---|---|---|---|---|---|',
    ]
    for r in a['tracking']['rows']:
        L.append(f'| {r["scenario"]} | {r["stack_controller"]} / {r["model_controller"]} | {_outc(r["stack_outcomes"])} | '
                 f'{_outc(r["model_outcomes"])} | {_mmx(r["stack_tracking_mean_m"])} | {_mmx(r["model_tracking_mean_m"])} |')
    L += [
        '',
        'In run 15 (`mislocalised`) the robot never moved in either world, so its tracking error is 0 by construction; '
        'one STACK RPP cell has no tracking samples at all (—). '
        'Outcomes agree in the hairpin, the crossing and run 15. They differ head-on by construction: Gazebo\'s person '
        'had no collision geometry and was driven through, the Arena\'s is solid. The model\'s controllers are smaller '
        '(DWA 11 × 21 samples against DWB\'s 819 per cycle, MPPI 128 rollouts against 2,000), so agreement of outcome is '
        'not agreement of mechanism.',
        '',
        '## The chips',
        '',
        'Wherever a lesson depends on one of these, the page shows a "model gap" chip that opens to this text and links '
        'here: the Arena\'s Localise, Map, Move and Decide lenses, and the Learn missions that use them.',
        '',
    ]
    for k, g in gaps(a).items():
        L.append(f'- **Model gap: {g["title"]}** — {g["text"]}')
    L += [
        '',
        '## Reproduce',
        '',
        '```',
        'python3 docs/v2/data/m2/m29/arena_fidelity.py ~/coco_lab_runs/lab2/fidelity_1 ~/coco_lab_runs/lab2/fidelity_s1 \\',
        f'    --out {SOURCE}',
        'python3 lab_web/tools/fidelity.py --write',
        '```',
        '',
        'The sessions live outside git (docs/data/lab2/README.md says how they were recorded); the JSON carries every '
        'number this report shows.',
    ]
    return '\n'.join(L) + '\n'


def _outc(o):
    return ', '.join(f'{n} {k.replace("_", " ")}' for k, n in sorted(o.items()))


def _mmx(s):
    if not s.get('n'):
        return '—'
    return f'{_m(s["median"])} [{_m(s["min"])}–{_m(s["max"])}] m'


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='write docs/v2/FIDELITY_v1.md')
    if ap.parse_args().write:
        with open(REPORT, 'w', encoding='utf-8') as f:
            f.write(report())
    for k, g in gaps().items():
        print(k, '|', g['text'])
