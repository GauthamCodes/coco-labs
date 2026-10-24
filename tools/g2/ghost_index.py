#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.6: the index of Race Nav2's ghosts (lab_web/public/stack/ghosts/index.json).

    tools/g2/ghost_index.py [--check]

Every ghost file there (tools/g2/make_ghost.py) is listed for each rules-4 phone seed that draws
its round (same start zone and orders), with its bytes and sha256. The page offers Race Nav2 for
a seed only when the index names a recording of that seed's round in which every leg succeeded.
G2 rules 5 (the model's actors stop for COCO) keeps rules 4's draw, so each rules-5 seed whose
round is a recording's (same start zone and orders) is listed too, for the same file: the
recording is the same Gazebo run (its actors parked), whatever the browser model's actors do.
"""
import argparse
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
from coco_lab import games  # noqa: E402

DIR = os.path.join(REPO, 'lab_web', 'public', 'stack', 'ghosts')


#: the rules whose rounds the recordings are offered for (rules 5: rules 4's draw, G2 rules 5)
RULES = (4, 5)


def build():
    docs = [(rules, games.load_rounds(rules=rules)) for rules in RULES
            if games.rounds_file(rules=rules).exists()]
    files = sorted(f for f in os.listdir(DIR) if f.endswith('.json') and f != 'index.json')
    entries = []
    for f in files:
        raw = open(os.path.join(DIR, f), 'rb').read()
        g = json.loads(raw)
        key = [g['round']['region'], g['round']['orders']]
        for rules, doc in docs:
            for mode, rounds in sorted(doc['rounds'].items()):
                for seed, r in sorted(rounds.items(), key=lambda kv: int(kv[0])):
                    if mode == g['round']['mode'] and [r['region'], r['orders']] == key:
                        entries.append({'file': f, 'rules': rules, 'mode': mode, 'seed': int(seed),
                                        'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                                        'driving_s': g['driving_s'], 'all_succeeded': g['all_succeeded'],
                                        'recorded_seed': g['round']['seed']})
    return {'schema': 'coco_lab.stack_ghosts', 'version': 1, 'evidence': 'STACK',
            'about': 'Race Nav2: recorded Gazebo + Nav2 runs of Fetch Rush rounds (tools/g2/record_ghosts.sh); '
                     'driving legs only, no grasp; Gazebo actors parked; never hardware',
            'ghosts': sorted(entries, key=lambda e: (e['rules'], e['mode'], e['seed']))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--check', action='store_true')
    o = ap.parse_args()
    text = json.dumps(build(), indent=1, sort_keys=True) + '\n'
    path = os.path.join(DIR, 'index.json')
    if o.check:
        same = os.path.exists(path) and open(path).read() == text
        print('ghost index is current' if same else 'ghost index is stale: run tools/g2/ghost_index.py')
        return 0 if same else 1
    with open(path, 'w') as f:
        f.write(text)
    print('wrote', path, [(e['seed'], e['file'], e['all_succeeded']) for e in json.loads(text)['ghosts']])
    return 0


if __name__ == '__main__':
    sys.exit(main())
