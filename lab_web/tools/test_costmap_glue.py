# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""Optional Compare inflation emits layers without touching either hash version."""
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('hash_version', [1, 2])
def test_inflated_compare_is_independent_and_emits_all_cells(hash_version):
    spec = importlib.util.spec_from_file_location(
        'costmap_test_glue', REPO / 'lab_web/src/arena/arena_glue.py')
    glue = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(glue)
    world = yaml.safe_load((REPO / 'worlds/coco_arena_v1.yaml').read_text())
    counts, headers, costs = [], [], set()

    def family(numeric, metadata):
        meta = json.loads(metadata)
        if 'header' in meta:
            headers.append(meta['header'])
        else:
            counts.append(len(numeric['seq']))
            costs.update(numeric['combined_cost'])

    glue.init(json.dumps(world), 3, 'astar', lambda *_: None,
              post_family=family, hash_version=hash_version)
    a = glue._arena
    before = a.state_bytes(), a.state_hash(), a.chain, a.grid
    result = json.loads(glue.compare('astar', 'dijkstra', 2.5, 2,
                                    lambda *_: None, 2048, json.dumps({
                                        'inflation_radius': 0.5,
                                        'cost_scaling_factor': 10,
                                        'robot_radius': 0.25})))
    assert (a.state_bytes(), a.state_hash(), a.chain, a.grid) == before
    assert result['A']['summary']['path_cost'] == pytest.approx(
        result['B']['summary']['path_cost'])
    assert sum(counts) == a.lab_map.width * a.lab_map.height
    assert max(counts) <= 2048
    assert {0, 253, 254} <= costs
    assert len(headers) == 1 and headers[0]['robot_radius'] == 0.25
