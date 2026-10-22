# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
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
#: the first two goals' searches, the big one (6,018 expansions) at tick 1879 among them
TICKS = 2000


def _run(how):
    a = Arena(DEPOT, REC['seed'], hash_version=REC['hash_version'])
    by = {}
    for e in REC['inputs']:
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
    for how in ('full', 'part', 'stale'):
        got, adopted = _run(how)
        assert adopted > 0, f'{how}: the test did not prefetch'
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
