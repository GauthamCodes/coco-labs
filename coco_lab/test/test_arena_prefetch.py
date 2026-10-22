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
G1.12: Arena.prefetch -- a goal's search run between ticks -- never changes the run.

A tick whose goal search has the prefetched key takes it over (finished, or where it got
to); a different key starts afresh. Either way every tick's state hash, every plan's path
and summary, and the hash chain are what they are without a prefetch.
"""
import json
from pathlib import Path

from coco_lab import games, loc_arena  # noqa: F401 -- loc_arena: the subsystem
from coco_lab.arena import Arena, ArenaError, InputEvent
import pytest

REPO = Path(__file__).resolve().parents[2]
DEPOT = json.loads((REPO / 'worlds' / 'coco_depot_v1.json').read_text())
REC = games.round_for(1)['reference']['record']     # rules 2, hash v3: AUTO-style goals
#: the record's goal inputs: the first, and the big one (6,018 expansions; tick 1879 there),
#: issued here at ticks 2 and 40 of an 80-tick run from the round's start (CI time)
GOALS = [e for e in REC['inputs'] if e['kind'] == 'goal']
SCRIPT = [dict(e, tick=0) for e in REC['inputs'] if e['tick'] == 0] + \
    [dict(GOALS[0], tick=2), dict(next(g for g in GOALS if g['tick'] == 1879), tick=40)]
TICKS = 80


def _run(how):
    a = Arena(DEPOT, REC['seed'], hash_version=REC['hash_version'])
    by = {}
    for e in SCRIPT:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    out, adopted = [], 0
    for k in range(TICKS):
        ev = by.get(a.tick, ())
        goals = [e for e in ev if e.kind == 'goal']
        if how and goals:
            g = goals[0]
            if how == 'full':
                assert a.prefetch((g.x, g.y)) is True
            elif how == 'part':
                a.prefetch((g.x, g.y), 40)
            elif how == 'stale':
                a.prefetch((g.x + 3.0, g.y))          # another goal: must not be taken over
            adopted += a._ahead is not None
        t = a.step(ev)
        out.append((t.state_hash, [(p.result.path, p.result.trace.summary) for p in t.plans]))
    return out, adopted


def test_prefetch_never_changes_a_tick():
    base, _ = _run(None)
    assert sum(len(p) for _, p in base) == 2 and all(r[0] for _, p in base for r in p)
    for how in ('full', 'part', 'stale'):
        got, adopted = _run(how)
        # a stale goal shifted onto no free cell prefetches nothing: one is enough there
        assert adopted == 2 or (how == 'stale' and adopted >= 1), f'{how}: no prefetch'
        assert got == base, f'{how}: a prefetch changed the run'


def test_a_finished_prefetch_is_taken_over():
    a = Arena(DEPOT, REC['seed'], hash_version=3)
    a.step([InputEvent(**e) for e in games.setup_inputs('fetch_rush', 1, 2)])
    goal = (30.0, 12.0)
    assert a.prefetch(goal) is True
    collector = a._ahead[1]
    a.begin_step([InputEvent(tick=a.tick, kind='goal', x=goal[0], y=goal[1])])
    assert a._collector is collector and a._ahead is None
    t = a.finish_step()
    assert t.plans and t.plans[0].result.found


def test_prefetch_is_not_part_of_the_state_and_not_inside_a_step():
    a = Arena(DEPOT, REC['seed'], hash_version=3)
    a.step([InputEvent(**e) for e in games.setup_inputs('fetch_rush', 1, 2)])
    h = a.state_hash()
    a.prefetch((30.0, 12.0), 100)
    assert a.state_hash() == h
    a.begin_step()
    with pytest.raises(ArenaError, match='inside a step'):
        a.prefetch((30.0, 12.0))
    a.finish_step()
