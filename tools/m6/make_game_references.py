#!/usr/bin/env python3
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
Run the reference bots on the Depot and commit their records and results (M6F.6).

    make_game_references.py [--check] [--seeds 1 2 3]

Writes ``docs/v2/m6/data/games_reference.json``: for each Fetch Rush seed and each
Rush Hour objective, the bot's input log (the record) and the result
(scorecard, state-hash chain, last hash). Stars for any player come from these
(``coco_lab.games.stars``). ``--check`` replays every committed record with
``coco_lab.games.verify`` (link limits, then a full replay) and fails on any
difference. Evidence class MODEL; a CPU run, so the machine state is recorded.
"""

import json
import os
import sys
import time

import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
from coco_lab import games  # noqa: E402, I100

OUT = os.path.join(REPO, 'docs', 'v2', 'm6', 'data', 'games_reference.json')
SPEC = os.path.join(REPO, 'worlds', 'coco_depot_v1.yaml')


def main():
    args = sys.argv[1:]
    seeds = [int(s) for s in args[args.index('--seeds') + 1:]] if '--seeds' in args \
        else [1, 2, 3]
    with open(SPEC, encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    if '--check' in args:
        with open(OUT, encoding='utf-8') as f:
            ref = json.load(f)
        bad = []
        for e in ref['runs']:
            ok = games.verify(spec, e['record'], e['result'])
            print(e['name'], 'reproduces' if ok else 'DIFFERS')
            bad += [] if ok else [e['name']]
        return 1 if bad else 0
    runs = []
    for seed in seeds:
        t0 = time.time()
        rec, res = games.bot_fetch_rush(spec, seed)
        runs.append({'name': f'fetch_rush_seed_{seed}', 'record': rec, 'result': res,
                     'bot_seconds': round(time.time() - t0, 1)})
        print(runs[-1]['name'], {k: res['scorecard'][k] for k in
                                 ('deliveries', 'contacts', 'time_used', 'path_efficiency')})
    for objective in sorted(games.RUSH_HOUR):
        t0 = time.time()
        rec, res = games.bot_rush_hour(spec, objective)
        runs.append({'name': f'rush_hour_{objective}', 'record': rec, 'result': res,
                     'bot_seconds': round(time.time() - t0, 1)})
        print(runs[-1]['name'], {k: res['scorecard'][k] for k in
                                 ('delivered', 'time', 'min_clearance', 'contacts',
                                  'jerk_rms')})
    out = {'schema': 'coco_lab.m6f.games_reference', 'version': 1,
           'spec': 'worlds/coco_depot_v1.yaml', 'evidence': 'MODEL',
           'bot': 'coco_lab.games.bot_fetch_rush / bot_rush_hour (planner + Grasp Assist)',
           'machine': {'load_average': os.getloadavg(), 'nice': os.nice(0)},
           'runs': runs}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write('\n')
    print(OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
