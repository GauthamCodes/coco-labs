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
G2.1: Fetch Rush rules 4 -- routes cross the forklift lane only at a marked crossing.

Gautham's decision (2026-10-23) and planning answer (2026-10-24): a route may enter the
east-west forklift lane (``games.ROUND_LANES``) only on a marked crossing (the hazard stripes
where a walker's lane crosses it, ``games.crossings``), with COCO's whole footprint on the
stripes (``games.crossing_bands``), and every stretch inside the lane crosses it -- never runs
along it. The rounds file (``coco_lab/levels/coco_depot_v1.fetch_rush.r4.json``) is written by
``tools/g2/make_fetch_rush_rounds_r4.py``; rules 3's file and records stay as they were.
"""
import hashlib
import json
from pathlib import Path

from coco_lab import games, loc_arena  # noqa: F401 -- loc_arena: the subsystem
from coco_lab.arena import Arena, InputEvent
import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO / 'worlds' / 'coco_depot_v1.json'
SPEC = json.loads(SPEC_PATH.read_text())
SPEC_V3 = Arena(SPEC, 1).spec      # normalized (map frame), as the rules see it
DOC = games.load_rounds(rules=4)
ROUNDS = [(mode, seed) for mode in sorted(DOC['rounds'])
          for seed in sorted(DOC['rounds'][mode], key=int)]
LANES = [games.zone_rect(SPEC_V3, z) for z in games.ROUND_LANES]
BANDS = games.crossing_bands(SPEC_V3)
CELL = 0.1


def test_the_rounds_are_for_this_level_and_these_rules():
    assert DOC['spec_sha256'] == hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
    assert DOC['rules'] == 4 and games.FETCH_RUSH_RULES == 5  # G2 rules 5: the browser's rules
    assert DOC['modes'] == games.ROUND_MODES_R4 == games.round_modes(4)
    assert DOC['timer_factor'] == games.ROUND_TIMER_FACTOR == 1.5
    assert DOC['lanes'] == list(games.ROUND_LANES) == ['zone_forklift_lanes']
    assert [tuple(c) for c in DOC['crossings']] == games.crossings(SPEC_V3)
    assert [tuple(b) for b in DOC['crossing_bands']] == BANDS
    assert DOC['crossing_windows'] == games.crossing_windows(Arena(SPEC, 1, hash_version=3))


#: the crossings a route may use: those with a contact-free window (measured, on file)
OPEN = [tuple(w['band']) for w in DOC['crossing_windows'] if w['open']]


def test_a_crossing_is_open_only_with_a_measured_window():
    """
    Close both Depot crossings: no start time has a contact-free window.

    Measured (games.crossing_windows): a straight crossing at the auto speed, from each of 600
    start times; on the Depot both marked crossings are the walkers' own paths, paced end to
    end, so none of the start times keeps COCO clear of the walker. Both are closed.
    """
    for w in DOC['crossing_windows']:
        assert w['of'] == games.CROSSING_WINDOW_TICKS == 600
        assert w['open'] == (w['clear_starts'] > 0)
    assert OPEN == [], 'the Depot as it is: no crossing has a contact-free window'
    assert {m: sorted(DOC['rounds'][m], key=int) for m in DOC['rounds']} == \
        {'full': ['1', '2', '3', '4', '5', '6'], 'phone': ['1', '2', '3', '4', '5', '6']}


def test_the_crossings_are_where_the_walkers_cross_the_east_west_lane():
    """Two crossings, each 1 m wide (a walker's lane), across the lane zone's whole depth."""
    lane = LANES[0]
    assert len(games.crossings(SPEC_V3)) == 2
    for (x0, x1, y0, y1), (b0, b1, _, _) in zip(games.crossings(SPEC_V3), BANDS):
        assert (y0, y1) == (lane[2], lane[3])
        assert abs((x1 - x0) - 1.0) < 1e-9
        r = SPEC_V3['robot']['radius']
        assert abs(b0 - (x0 + r)) < 1e-9 and abs(b1 - (x1 - r)) < 1e-9
    walkers = [k for k in SPEC_V3['kit'] if k.get('actor') == 'walker']
    assert sorted(round((c[0] + c[1]) / 2, 6) for c in games.crossings(SPEC_V3)) == \
        sorted(round(w['path'][0][0], 6) for w in walkers)


def _cells(route):
    """Return the route's cell centres: each merged segment is a straight or diagonal run."""
    out = [tuple(route[0])]
    for (x0, y0), (x1, y1) in zip(route, route[1:]):
        n = max(1, round(max(abs(x1 - x0), abs(y1 - y0)) / CELL))
        out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(1, n + 1)]
    return out


def _keeps_the_rule(points):
    """Return why ``points`` (a route's cells or a run's poses) break the crossing rule or None."""
    inside, came = None, None
    last_out = None
    for p in points:
        rect = next((r for r in LANES if games.in_rect(p, r)), None)
        if rect is not None:
            if not any(games.in_rect(p, b) for b in OPEN):
                return f'in the lane off a crossing at {p}'
            if inside is None:
                inside, came = rect, (games.lane_side(last_out, rect) if last_out else None)
        else:
            if inside is not None and came is not None and games.lane_side(p, inside) == came:
                return f'left a crossing on the side it came in at {p}'
            inside, last_out = None, p
    return None


@pytest.mark.parametrize('mode,seed', ROUNDS)
def test_each_round_keeps_the_decisions(mode, seed):
    m = games.ROUND_MODES_R4[mode]
    rnd = DOC['rounds'][mode][seed]
    drawn = games.draw_round(int(seed), DOC['trips'], m['budget_m'], m['orders'], rnd['attempt'])
    assert drawn == {'region': rnd['region'], 'orders': rnd['orders']}
    assert [r['attempt'] for r in rnd['rejected']] == list(range(rnd['attempt']))
    assert rnd['region'] not in games.ROUND_NO_START
    assert len(rnd['orders']) == m['orders'] == len(rnd['pick']) == len(rnd['via'])
    frm = rnd['region']
    for (oid, drop), ghost, route, via in zip(rnd['orders'], rnd['ghost_m'], rnd['routes'],
                                              rnd['via']):
        assert ghost == DOC['trips'][frm][oid][drop] <= m['budget_m']
        why = _keeps_the_rule(_cells(route))
        assert why is None, f'{mode} {seed}: the route {why}'
        # the bot's goals: crossing mouths on a band's centre line, outside the lane
        for leg in via:
            for p in leg:
                assert not any(games.in_rect(p, r) for r in LANES)
                assert any(abs(p[0] - (b[0] + b[1]) / 2) < 1e-3 for b in BANDS)
        frm = drop
    card = rnd['reference']['card']
    assert card['deliveries'] == m['orders'] and card['rules'] == 4 and card['mode'] == mode
    assert rnd['timer_s'] == round(rnd['reference_time_s'] * games.ROUND_TIMER_FACTOR, 1)
    assert (card['timer'] == rnd['timer_s']
            and card['delivered'][-1]['t'] == rnd['reference_time_s'])
    rec = rnd['reference']['record']
    assert rec['rules'] == 4 and rec['mode'] == mode and rec['hash_version'] == 3


@pytest.mark.parametrize('mode,seed', ROUNDS)
def test_the_reference_bot_kept_the_crossing_rule(mode, seed):
    """Its run, replayed tick by tick: COCO in the lane only on a band, and only crossing it."""
    rec = DOC['rounds'][mode][seed]['reference']['record']
    a = Arena(SPEC, rec['seed'], hash_version=rec['hash_version'])
    by = {}
    for e in rec['inputs']:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    poses = []
    for _ in range(rec['ticks']):
        a.step(by.get(a.tick, ()))
        poses.append(tuple(a.pose[:2]))
    assert _keeps_the_rule(poses) is None


@pytest.mark.parametrize('mode', ['phone', 'full'])
def test_the_reference_record_replays_to_its_card(mode):
    rnd = games.round_for(1, rules=4, mode=mode)
    got = games.play(SPEC, rnd['reference']['record'])
    assert got['scorecard'] == rnd['reference']['card']
    assert got['hash_chain'] == rnd['reference']['hash_chain']


def test_rules_3_is_untouched():
    """Rules 3's rounds still load and replay as they were (records made before G2.1)."""
    rnd = games.round_for(1, rules=3, mode='phone')
    assert games.round_modes(3) == games.ROUND_MODES and rnd['timer_s'] == 273.5
    got = games.play(SPEC, rnd['reference']['record'])
    assert got['hash_chain'] == rnd['reference']['hash_chain']


def test_the_lane_grid_blocks_the_lane_off_the_bands_only():
    from coco_lab import numerics
    a = Arena(SPEC, 1, hash_version=3)
    with numerics.version(3):
        g = games.lane_grid(a)
    pm = a.plan_map
    for i in range(0, g.width * g.height, 7):
        xy = pm.cell_centre(i // g.width, i % g.width)
        in_lane = any(games.in_rect(xy, r) for r in LANES)
        on_band = any(games.in_rect(xy, b) for b in BANDS)
        want = a.grid._blocked[i] or (in_lane and not on_band)
        assert g._blocked[i] == want
