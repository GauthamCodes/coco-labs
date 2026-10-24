#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2 rules 5: replay every committed Fetch Rush reference record of RULES; compare card and chain.

    tools/g2/replay_references.py RULES      (2, 3, 4 or 5)
"""
import os
import json
import sys
import time
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
from coco_lab import games  # noqa: E402
spec = json.load(open(os.path.join(REPO, 'worlds', 'coco_depot_v1.json')))
rules = int(sys.argv[1])
doc = games.load_rounds(rules=rules)
rounds = doc['rounds']
items = []
if rules == 2:
    items = [(None, s, r) for s, r in sorted(rounds.items(), key=lambda kv: int(kv[0]))]
else:
    items = [(m, s, r) for m in sorted(rounds) for s, r in sorted(rounds[m].items(), key=lambda kv: int(kv[0]))]
ok = bad = skipped = 0
for m, s, r in items:
    ref = r.get('reference')
    if not ref or 'record' not in ref:
        skipped += 1; print(rules, m, s, 'no reference', flush=True); continue
    t0 = time.time()
    got = games.play(spec, ref['record'])
    same = got['hash_chain'] == ref['hash_chain'] and got['scorecard'] == ref['card']
    ok += same; bad += not same
    print(rules, m, s, 'IDENTICAL' if same else 'DIFFERENT', ref['record']['ticks'], f'{time.time() - t0:.0f} s', flush=True)
print(f'rules {rules}: {ok} identical, {bad} different, {skipped} without a reference', flush=True)
