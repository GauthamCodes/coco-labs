# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""Independent cell-distance/formula calculation on emitted browser layers."""
import json
import gzip
import math
from pathlib import Path
import sys

out = Path(sys.argv[1])
raw = out / 'costmap-emitted.json'
messages = json.loads(raw.read_text() if raw.exists() else gzip.decompress(raw.with_suffix('.json.gz').read_bytes()))
header = next(m['header'] for m in messages if 'header' in m)
cells = {}
for message in messages:
    c = message.get('columns')
    if c:
        for i, (row, col) in enumerate(zip(c['row'], c['col'])):
            cells[int(row), int(col)] = {k: int(c[k][i]) for k in ['static_cost', 'obstacle_cost', 'inflation_cost', 'combined_cost']}
occupied = {pos for pos, costs in cells.items() if max(costs['static_cost'], costs['obstacle_cost']) == 254}
resolution = float(header['resolution'])
radius = float(header['robot_radius'])
inflation = float(header['inflation_radius'])
scaling = float(header['cost_scaling_factor'])
chosen = {}
limit = math.ceil(.6 / resolution)
offsets = sorted((math.hypot(dr, dc) * resolution, dr, dc) for dr in range(-limit, limit+1) for dc in range(-limit, limit+1))
# Representative centre distances in metres, independently from the EDT.
for pos, costs in cells.items():
    distance = next((distance for distance, dr, dc in offsets if (pos[0]+dr, pos[1]+dc) in occupied), math.inf)
    for target in [0, .2, .25, .3, .35, .5, .55]:
        if target in chosen:
            continue
        if abs(distance - target) > 1e-10:
            continue
        formula = 254 if distance == 0 else 0 if distance > inflation else 253 if distance <= radius else int(252 * math.exp(-scaling * (distance - radius)))
        # The inflation-only channel excludes lethal source cells by design.
        expected_inflation = 0 if distance == 0 else formula
        chosen[target] = {'cell': pos, 'distance_m': distance, 'formula': formula,
                          'emitted': costs, 'expected_inflation': expected_inflation,
                          'passed': costs['combined_cost'] == formula and costs['inflation_cost'] == expected_inflation}
    if len(chosen) == 7:
        break
report = {'header': header, 'source_cells': len(occupied), 'method': 'brute-force Euclidean distance to emitted static/obstacle lethal cells; 254, 253, truncated 252*exp(-k*(d-r)); no coco_lab costmap function imported', 'cells': list(chosen.values()), 'passed': len(chosen) == 7 and all(r['passed'] for r in chosen.values())}
(out / 'costmap-hand-check.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
if not report['passed']:
    sys.exit(1)
