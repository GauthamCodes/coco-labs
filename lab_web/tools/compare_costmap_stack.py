#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""Compare MODEL inflation with committed STACK snapshots, never edit them.

PYTHONPATH=coco_lab python lab_web/tools/compare_costmap_stack.py --out FILE
Not a reconstruction of the Stack obstacle layers: use each snapshot's
lethal cells as seeds, exclude unknown cells from scoring. Parameters come
from the committed global-costmap configuration, not a fitted optimum.
"""
import argparse
from dataclasses import asdict
import gzip
import hashlib
import json
import math
from pathlib import Path

from coco_lab.costmap import InflationParams, build_layers

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / 'docs/data/lab5/snapshot_c1'


def compare(path):
    with gzip.open(path, 'rt') as stream:
        snapshot = json.load(stream)
    w, h, r = (snapshot[k] for k in ('width', 'height', 'resolution'))
    # ROS OccupancyGrid order (south first). Layers are built in that same
    # order for this scalar comparison; no browser coordinate conversion.
    recorded = snapshot['data']
    seeds = [v == 254 for v in recorded]
    eligible = [i for i, v in enumerate(recorded) if v != 255]
    profiles = {}
    for name, radius in [('circular_radius_0_20', 0.20),
                         ('padded_16gon_apothem', 0.21 * math.cos(math.pi / 16))]:
        p = InflationParams(0.5, 5, radius)
        layers = build_layers(w, h, r, seeds, params=p)
        errors = [abs(layers.combined[i] - recorded[i]) for i in eligible]
        profiles[name] = {
            'params': asdict(p), 'compared_known_cells': len(eligible),
            'identical_cells': sum(e == 0 for e in errors),
            'different_cells': sum(e != 0 for e in errors),
            'mean_absolute_cost_error': sum(errors) / len(errors),
            'maximum_absolute_cost_error': max(errors),
            'lethal_seeds': sum(seeds),
        }
    return {'source': str(path.relative_to(REPO)),
            'source_file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'recorded_content_hash': snapshot['content_hash'],
            'dimensions': [w, h], 'resolution_m': r, 'profiles': profiles}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = {
        'evidence': 'MODEL vs STACK',
        'method': 'Nearest recorded lethal-cell centres; unknown cells excluded.',
        'parameter_evidence': ['gazebo_models/config/nav2_params.yaml',
                               'docs/agents/C2-NAV.48_RESULTS.md'],
        'limits': ['Not temporal obstacle-layer replay or Stack equivalence.',
                   'Unknown-space inflation and footprint geometry differ.',
                   'Snapshot metadata pins historical configuration hashes; '
                   'current committed parameters are a declared comparison, '
                   'not proof of the historical merged runtime parameters.'],
        'snapshots': [compare(SOURCE / name) for name in
                      ['costmap_before.json.gz', 'costmap_after.json.gz']],
    }
    args.out.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
