# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""R5.5: a world-editor level (no actors, no objects) steps in Play's glue, every tick strict JSON (as JSON.parse)."""
import json
import os
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'lab_web' / 'src' / 'arena'))


def _strict(text):
    def refuse(c):
        raise ValueError(f'{c} is not JSON (JSON.parse refuses it)')
    return json.loads(text, parse_constant=refuse)


def test_an_editor_level_steps_with_strict_json_ticks(monkeypatch):
    monkeypatch.setenv('COCO_WORLDS', str(REPO / 'worlds'))
    import arena_glue as g
    from coco_lab.level_check import check
    depot = yaml.safe_load((REPO / 'worlds/coco_depot_v1.yaml').read_text(encoding='utf-8'))
    wall = lambda i, a, b: {'id': i, 'kind': 'wall', 'from': a, 'to': b, 'thickness': 0.15, 'height': 2.0}  # noqa: E731
    spec = {'spec_version': 'coco.world_spec.v3', 'id': 'editor_glue', 'title': 'glue', 'frame': 'world', 'world_to_map': [0.0, 0.0],
            'bounds': {'x_min': 0.0, 'x_max': 10.0, 'y_min': 0.0, 'y_max': 8.0}, 'robot': depot['robot'],
            'start': {'x': 2.0, 'y': 2.0, 'theta': 0.0}, 'arena': depot['arena'],
            'kit': [wall('s', [0, 0], [10, 0]), wall('n', [0, 8], [10, 8]), wall('w', [0, 0], [0, 8]), wall('e', [10, 0], [10, 8])]}
    lowered = check(spec, [[8, 6]])['spec']                     # as the editor's link carries it
    world = _strict(g.game_init(json.dumps(lowered), 'free', 0, 1, lambda *a, **k: None, 2048)[0])
    rows = [dict(r, tick=0) for r in world['game']['setup']] + [{'tick': 0, 'kind': 'goal', 'x': 8.0, 'y': 6.0}]
    moved = False
    for k in range(60):
        t = _strict(g.step(json.dumps(rows if k == 0 else []))[0])
        moved = moved or abs(t['pose'][0] - 2.0) > 0.05
    assert moved                                                # AUTO drives toward the goal
    assert 'clearance' not in (t.get('game') or {})             # no actors: no clearance, rather than Infinity
    os.environ.pop('COCO_WORLDS', None)
