#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Build Play's levels (M3.5) from lab_web/play/levels.src.yaml.

    python3 lab_web/tools/make_play_levels.py [--check]

Writes lab_web/play/levels.json and docs/v2/CHALLENGES.md. Every number a
star is measured against is computed here by coco_lab.play -- the reference
algorithms run on the level -- and nothing is typed:

- beat-the-planner: A*'s optimal cost and expansions, weighted A*'s and
  greedy best-first's cost ratios;
- next-node: how many of A*'s next 10 expansions a least-g and a least-h
  predictor match;
- search-the-bays: the optimal order's expected cost, and the cost ratios
  of nearest-first and most-likely-first;
- map-the-arena: two reference drives (goals given on arrival, the input
  log recorded), each re-simulated by coco_lab.play.map_drive and scored;
- case-file-detective: the divergence moment, from the committed
  docs/v2/data/m3/m34/moments.json (re-derived from the Case File by
  lab_web/test/casefile_moments.test.ts).

``--check`` writes nothing and exits 1 if the committed files differ from
what this would write. Each level is refused unless its references set
the stars apart (the M3 prompt's B.5: a score must not reward luck, and a
star must mean something).
"""

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))

import yaml  # noqa: E402

from coco_lab import play  # noqa: E402
from coco_lab.fetch_problem import PROBLEM  # noqa: E402

SRC = os.path.join(REPO, 'lab_web', 'play', 'levels.src.yaml')
OUT = os.path.join(REPO, 'lab_web', 'play', 'levels.json')
DOC = os.path.join(REPO, 'docs', 'v2', 'CHALLENGES.md')
SPEC = os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml')
MOMENTS = os.path.join(REPO, 'docs', 'v2', 'data', 'm3', 'm34', 'moments.json')
#: a Case File plays one tick per 0.1 s of recorded time (src/arena/replay_case.ts)
TICK_S = 0.1
#: a reference drive gives up on a goal after this many ticks
GOAL_TICKS = 1500


class LevelError(ValueError):
    """A level whose stars would not mean anything."""


def spec():
    with open(SPEC, encoding='utf-8') as f:
        return yaml.safe_load(f)


def drive_log(sp, level, goals):
    """Drive the goals in turn, each given when the last is reached; return the input log."""
    from coco_lab.arena import Arena, InputEvent
    from coco_lab import loc_arena, map_arena, move_arena, mission_arena  # noqa: F401
    a = Arena(sp, int(level['seed']))
    budget = play.MapBudget(level['budget_m'], a.pose)
    log = [{'tick': 0, 'kind': 'config', 'choice': c} for c in level['config']]
    log.append({'tick': 0, 'kind': 'goal', 'x': goals[0][0], 'y': goals[0][1]})
    pending = [InputEvent(**r) for r in log]
    gi, k, since = 1, 0, 0
    while k < level['max_ticks']:
        t = a.step(pending)
        pending = []
        k += 1
        since += 1
        if budget.update(a.pose):
            break
        if (t.arrived or since >= GOAL_TICKS) and gi < len(goals):
            log.append({'tick': k, 'kind': 'goal', 'x': goals[gi][0], 'y': goals[gi][1]})
            pending.append(InputEvent(**log[-1]))
            gi, since = gi + 1, 0
        elif (t.arrived or since >= GOAL_TICKS) and gi == len(goals):
            break
    return {'goals': goals, 'inputs': log, 'ticks': k}


def build():
    with open(SRC, encoding='utf-8') as f:
        src = yaml.safe_load(f)
    with open(MOMENTS, encoding='utf-8') as f:
        moments = json.load(f)
    sp = spec()
    out = {'schema': play.LEVELS_SCHEMA, 'source': 'lab_web/play/levels.src.yaml',
           'tool': 'lab_web/tools/make_play_levels.py', 'order': list(play.CHALLENGES), 'challenges': {}}
    for cid in play.CHALLENGES:
        c = src['challenges'][cid]
        levels = []
        for lv in c['levels']:
            lv = copy.deepcopy(lv)
            if cid == 'search-the-bays':
                p = copy.deepcopy(PROBLEM)
                p['prior'] = lv.pop('prior')
                p['detection'] = [lv.pop('detection')] * len(p['regions'])
                lv['problem'] = p
            if cid == 'map-the-arena':
                lv['spec'] = play._spec_hash(sp)
                lv['drives'] = {k: drive_log(sp, lv, g) for k, g in lv['drives'].items()}
            if cid == 'case-file-detective':
                m = moments['casefiles'].get(lv['casefile'])
                if not m or not m.get('divergence'):
                    raise LevelError(f"{lv['id']}: {lv['casefile']} has no divergence moment in {MOMENTS}")
                lv.update(moment={'tick': m['divergence']['tick'], 't_world': m['divergence']['t_world'],
                                  'error_m': play._r(m['divergence']['error_m']), 'source': m['divergence']['source']},
                          ticks=m['ticks'], tick_s=TICK_S, tolerance_s=c['tolerance_s'],
                          bands_s=c['bands_s'], divergence_m=moments['divergence_m'])
            else:
                lv['reference'] = play.references(lv, cid, sp)
            check(cid, lv)
            levels.append(lv)
        out['challenges'][cid] = {'title': c['title'], 'goal': ' '.join(c['goal'].split()), 'levels': levels}
    return out


def check(cid, lv):
    """Refuse a level whose reference thresholds do not separate the stars."""
    r = lv.get('reference', {})
    if cid == 'beat-the-planner':
        ok = 1 + play.EPS < r['weighted_astar_ratio'] < r['greedy_ratio'] - play.EPS
    elif cid == 'next-node':
        lo, hi = sorted((r['min_g_matches'], r['min_h_matches']))
        ok = 1 <= lo < hi < play.NEXT_N
    elif cid == 'search-the-bays':
        hi, lo = sorted((r['nearest_ratio'], r['most_likely_ratio']))
        ok = 1 + play.EPS < hi < lo - play.EPS
    elif cid == 'map-the-arena':
        a, b = sorted((r['out_and_back']['f1'], r['tour']['f1']))
        ok = 0 < a < b
    else:
        b = lv['bands_s']
        ok = b[0] > b[1] > b[2] > 0 and lv['tolerance_s'] in b
    if not ok:
        raise LevelError(f"{cid}/{lv['id']}: its references do not set the stars apart: {r}")


def fmt(v):
    return f'{v:.4f}' if isinstance(v, float) else str(v)


def doc(levels):
    L = ['# Play: the five challenges (M3.5)', '',
         'Generated by `lab_web/tools/make_play_levels.py` from `lab_web/play/levels.src.yaml`;',
         'do not edit. Scored by `coco_lab/coco_lab/play.py` -- in the page (the Arena',
         "worker, Pyodide), by `coco verify` (Pyodide in Node) and by the tests (CPython): one",
         'implementation. Every star threshold below is a **reference algorithm\'s result on that',
         'level**, computed by the tool, never chosen.', '',
         '**Rules for every challenge**', '',
         '- A score is a pure function of the level and your inputs: no random draw, no wall time.',
         '  The page shows it broken down into its named metrics.',
         '- Computation is counted in expansions, within this one implementation, never timed.',
         '- A challenge link carries the level\'s hash and your whole input log; opening it re-scores',
         '  the run and says whether it reproduced exactly (the same result hash).',
         '- Personal bests stay in your browser (every storage access in try/catch); the page works',
         '  without storage. No server, no accounts, no leaderboard.',
         '- Stars are cumulative: the second needs the first threshold too.', '']
    ch = levels['challenges']

    L += ['## Beat the planner', '', ch['beat-the-planner']['goal'], '',
          '**Score:** your path\'s cost / the optimal cost. A path is a chain of legal moves',
          '(8-connected, no corner cutting); a move costs its length times',
          f'`1 + 2 x cost / 252`, a cost digit d being d x {play.COST_PER_DIGIT:g}.', '',
          '| level | optimal cost | A* expansions | ★ greedy best-first | ★★ weighted A* | ★★★ A* |',
          '|---|---|---|---|---|---|']
    for lv in ch['beat-the-planner']['levels']:
        r = lv['reference']
        L.append(f"| {lv['title']} | {fmt(r['optimal_cost'])} | {r['astar_expansions']} | "
                 f"≤ {fmt(r['greedy_ratio'])} | ≤ {fmt(r['weighted_astar_ratio'])} (w = {lv['weight']:g}) | 1 |")

    L += ['', '## Next node', '', ch['next-node']['goal'], '',
          '**Score:** how many of A*\'s next 10 expansions you predicted. A* (octile heuristic)',
          'orders by f, then the lower h, then insertion order. You cannot see insertion order,',
          'so a prediction counts if it is open and has the same (f, h) as the cell A* expanded:',
          'any such cell is one A* could have taken. Luck plays no part.', '',
          '| level | after | ★ the weaker predictor | ★★ the stronger | ★★★ A* itself |',
          '|---|---|---|---|---|']
    for lv in ch['next-node']['levels']:
        r = lv['reference']
        lo, hi = sorted((r['min_g_matches'], r['min_h_matches']))
        L.append(f"| {lv['title']} | {lv['after']} expansions | ≥ {lo} | ≥ {hi} | 10 |")
    L += ['', 'The predictors: always the open cell of least g (Dijkstra\'s choice), always the',
          'one of least h (greedy\'s).']

    L += ['', '## Search the bays', '', ch['search-the-bays']['goal'], '',
          '**Score:** the expected cost of your order / the least expected cost of any order',
          '(`coco_lab.regionsearch.plan_cost`, `optimal_order`: every order costed exactly).',
          'Expected over the prior, so it **never rewards luck**: the order is judged before',
          'anything is found. The travel costs are the Arena\'s own (`fetch_problem.py`).', '',
          '| level | prior | d | optimal E[cost] (m) | ★ the worse simple policy | ★★ the better | ★★★ optimal |',
          '|---|---|---|---|---|---|---|']
    for lv in ch['search-the-bays']['levels']:
        r = lv['reference']
        hi, lo = sorted((r['nearest_ratio'], r['most_likely_ratio']))
        L.append(f"| {lv['title']} | {lv['problem']['prior']} | {lv['problem']['detection'][0]} | "
                 f"{fmt(r['optimal_expected'])} | ≤ {fmt(lo)} | ≤ {fmt(hi)} | 1 |")
    L += ['', 'The simple policies: nearest first, and most likely first (`regionsearch.policy_plan`).']

    L += ['', '## Map the arena', '', ch['map-the-arena']['goal'], '',
          '**Score:** the map\'s F1 and the trajectory\'s ATE (Lab 3\'s scores,',
          '`coco_lab.mapeval`, as the Arena\'s Map lens computes them), at the tick the',
          'ground-truth distance driven reaches the budget, or when you finish. Your drive is',
          're-simulated from its input log; the only config lines it may hold are the level\'s, at',
          'tick 0, and it may not kidnap or reset. The noise is fixed by the level\'s seed, so a',
          'drive scores the same every time.', '',
          '| level | budget | config | ★ the weaker drive\'s F1 | ★★ the stronger\'s F1 | ★★★ the stronger\'s F1 and ATE |',
          '|---|---|---|---|---|---|']
    for lv in ch['map-the-arena']['levels']:
        r = lv['reference']
        w, s = sorted((r['out_and_back'], r['tour']), key=lambda d: d['f1'])
        L.append(f"| {lv['title']} | {lv['budget_m']:g} m | `{' '.join(lv['config'])}` | ≥ {fmt(w['f1'])} | "
                 f"≥ {fmt(s['f1'])} | ≥ {fmt(s['f1'])} and ATE ≤ {fmt(s['ate'])} m |")
    L += ['', 'The reference drives: out and back, and a tour of six free spots (goals given on',
          'arrival); their goals and input logs are in `lab_web/play/levels.json`.']
    for lv in ch['map-the-arena']['levels']:
        r = lv['reference']
        L.append(f"- {lv['title']}: out and back F1 {fmt(r['out_and_back']['f1'])}, ATE "
                 f"{fmt(r['out_and_back']['ate'])} m, {fmt(r['out_and_back']['path_m'])} m; the tour F1 "
                 f"{fmt(r['tour']['f1'])}, ATE {fmt(r['tour']['ate'])} m, {fmt(r['tour']['path_m'])} m.")

    c = ch['case-file-detective']
    L += ['', '## Case File detective', '', c['goal'], '',
          '**Score:** how far your tick is from the divergence, in recorded seconds. The',
          'divergence is the first tick at which the stack\'s belief (AMCL, when recorded) is more',
          f"than {c['levels'][0]['divergence_m']:g} m from ground truth (`lab_web/src/arena/moments.ts`, "
          're-derived in CI from the committed Case File).', '',
          f"**Stated tolerance:** {c['levels'][0]['tolerance_s']:g} s (\"found\"). The stars are "
          'bands around the reference rule\'s answer, which scores 0 s: this is the one challenge',
          'whose reference is a rule with an exact answer rather than competing algorithms.', '',
          '| level | Case File | divergence tick | gap at divergence | ★ | ★★ | ★★★ |',
          '|---|---|---|---|---|---|---|']
    for lv in c['levels']:
        b = lv['bands_s']
        L.append(f"| {lv['title']} | `{lv['casefile']}` | {lv['moment']['tick']} | {fmt(lv['moment']['error_m'])} m | "
                 f"within {b[0]:g} s | within {b[1]:g} s | within {b[2]:g} s |")
    L += ['', '## What is not here', '',
          'Lost robot, Gauntlet, Drive it yourself and Trade-off frontier are later ideas',
          '(`docs/IDEAS.md`), not M3 challenges.', '']
    return '\n'.join(L)


def main():
    levels = build()
    text = json.dumps(levels, indent=1, sort_keys=True) + '\n'
    md = doc(levels)
    if '--check' in sys.argv:
        bad = [p for p, t in ((OUT, text), (DOC, md)) if not os.path.exists(p) or open(p, encoding='utf-8').read() != t]
        for p in bad:
            print('STALE', os.path.relpath(p, REPO))
        raise SystemExit(1 if bad else 0)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(text)
    with open(DOC, 'w', encoding='utf-8') as f:
        f.write(md)
    n = sum(len(c['levels']) for c in levels['challenges'].values())
    print(f'{n} levels over {len(levels["challenges"])} challenges -> {os.path.relpath(OUT, REPO)}, {os.path.relpath(DOC, REPO)}')


if __name__ == '__main__':
    main()
