#!/usr/bin/env python3
import json
import os
import sys

sys.path.extend(['coco_sim', 'coco_config'])
from coco_sim.episode import generate_episode, EpisodeSpec, TargetSpec
from coco_config.robot import TargetRegion, region_by_id

# Generate base episode
spec = generate_episode(seed=99, level='colours', requested_colour='red')

from dataclasses import replace

# Swap red to bay_4 (+6.0m) and yellow to bay_2 (-2.0m)
targets = []
for t in spec.targets:
    if t.colour == 'red':
        reg = region_by_id('bay_4')
        targets.append(replace(t, region_id='bay_4', y=reg.bay_y))
    elif t.colour == 'yellow':
        reg = region_by_id('bay_2')
        targets.append(replace(t, region_id='bay_2', y=reg.bay_y))
    else:
        targets.append(t)

adv_spec = replace(spec, targets=tuple(targets), requested_colour='red')
out_path = '/home/gautham/coco_runs_p03c/adversarial_manifest.json'
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w') as f:
    f.write(adv_spec.to_json())

print(f"Generated adversarial manifest at {out_path}")
print("Region map:", adv_spec.region_map())
