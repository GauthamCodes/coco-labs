# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
How many committed determinism sessions mix autonomy with teleop (M4.3).

The reason M4.3 keeps M1's rule (teleop preempts autonomy the moment it
arrives) rather than changing it: any change to it would change the hashes
of every committed session in which a teleop input meets a goal. This counts
them, per committed session set. Usage:
``python3 docs/v2/data/m4/m43/count_mixed_sessions.py > docs/v2/data/m4/m43/mixed_sessions.json``
"""

import glob
import json
import os

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '..'))
out = {}
for path in sorted(glob.glob(os.path.join(REPO, 'docs', 'v2', 'data', '**', 'sessions.json'), recursive=True)):
    rel = os.path.relpath(path, REPO)
    if '/m4/' in rel:
        continue
    with open(path, encoding='utf-8') as f:
        sessions = json.load(f)['sessions']
    mixed = 0
    for s in sessions:
        kinds = [e['kind'] for e in sorted(s['inputs'], key=lambda e: e['tick'])]
        # a teleop after a goal, or a goal after a teleop: the rule decides what happens
        if 'teleop' in kinds and 'goal' in kinds:
            mixed += 1
    out[rel] = {'sessions': len(sessions), 'with_goal_and_teleop': mixed}
print(json.dumps(out, indent=1))
