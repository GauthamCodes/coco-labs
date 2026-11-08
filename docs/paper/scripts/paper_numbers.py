#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.7: every number in the paper, as a LaTeX macro computed from committed data.

    python docs/paper/scripts/paper_numbers.py            write docs/paper/generated/numbers.tex
    python docs/paper/scripts/paper_numbers.py --check    fail if the committed file differs

Each macro names its source file (relative to the repository) and how the value is taken from
it; ``numbers.tex`` lists the source beside every macro, so a reader can check any number. The
paper's text may not type a number itself (``lint_tex.py``). A macro whose source is not yet
committed is an error, never a placeholder value.
"""
import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / 'docs' / 'paper' / 'generated' / 'numbers.tex'


def j(rel):
    return json.loads((REPO / rel).read_text())


def frac(a, b):
    return f'{a}/{b}'


def f(x, nd=3):
    return f'{x:.{nd}f}'


def suites_v1():
    return sorted((REPO / 'coco_lab' / 'coco_lab' / 'benchmarks').glob('*.v1.json'))


DET = 'docs/v2/r2/data/r29/determinism_v2.json'
PAR = 'docs/v2/r2/data/r29/r2_parity.json'
ESC = 'docs/v2/r2/data/r29/escape_{}.json'
R27 = 'docs/v2/r2/data/r27/summary.json'


def macros():
    """Return [(name, value, source)]: the paper's numbers."""
    out = []

    def add(name, value, source):
        out.append((name, str(value), source))

    det = j(DET)
    eng = det['engines']
    add('DetEngines', len(eng), DET)
    add('DetTicksPerEngine', eng['chromium']['ticks_compared'], DET)
    add('DetSessionsPerEngine', eng['chromium']['sessions'], DET)
    add('DetMismatches', sum(e['ticks_mismatched'] for e in eng.values()), DET)
    add('DetDigests', 'identical' if len({e['all_hashes_sha256'] for e in eng.values()}) == 1
        else 'different', DET)
    par = j(PAR)
    add('ParityValues', par['compared'], PAR)
    add('ParityDiffs', sum(c['differences'] for c in par['cases'].values()), PAR)
    add('ParityTemplates', len(par['cases']), PAR)
    esc = [j(ESC.format(b)) for b in ('chromium', 'firefox', 'webkit')]
    add('EscapeBrowsers', len(esc), ESC.format('*'))
    add('EscapeCases', len(esc[0]['cases']), ESC.format('chromium'))
    add('EscapeCasesSafe', min(sum(1 for c in e['cases'] if c['ok']) for e in esc),
        ESC.format('*'))
    add('EscapeProbes', len(esc[0]['probe']), ESC.format('chromium'))
    add('EscapeProbesBlocked', min(sum(1 for v in e['probe'].values() if v.startswith('blocked'))
                                   for e in esc), ESC.format('*'))
    s = j(R27)
    pl = s['planning']
    add('StackPlanRequests', pl['stock']['requests'], R27)
    add('StackPlanScenarios', len(j('docs/v2/r2/data/r27/depot20_plan.json')['scenarios']),
        'docs/v2/r2/data/r27/depot20_plan.json')
    add('StackPlanSessions', len(pl['stock']['sessions']), R27)
    add('StackDriveScenarios', len(j('docs/v2/r2/data/r27/depot5_drive.json')['scenarios']),
        'docs/v2/r2/data/r27/depot5_drive.json')
    add('StackPPRounds', len(s['controller']['rounds']), R27)
    add('StackPPRunsPerRound', max(int(v.split('/')[1]) for v in s['controller']['rounds'].values()),
        R27)
    add('StackStockPlans', frac(pl['stock']['succeeded'], pl['stock']['requests']), R27)
    add('StackAstarPlans', frac(pl['astar_starter']['succeeded'],
                                pl['astar_starter']['requests']), R27)
    add('StackThetaPlans', frac(pl['theta_star']['succeeded'], pl['theta_star']['requests']), R27)
    dr = s['drive']
    add('StackStockDrives', frac(dr['stock']['succeeded'], dr['stock']['goals']), R27)
    add('StackAstarDrives', frac(dr['coco_user_astar_starter']['succeeded'],
                                 dr['coco_user_astar_starter']['goals']), R27)
    add('StackThetaDrives', frac(dr['coco_user_theta_star']['succeeded'],
                                 dr['coco_user_theta_star']['goals']), R27)
    c = s['controller']
    add('StackPPLegs', frac(c['legs_succeeded'], c['legs']), R27)
    add('StackPPGapS', f(c['paired_leg_gap_s']['median'], 3), R27)
    add('StackPPGapN', c['paired_leg_gap_s']['n'], R27)
    # R3 Part A follow-ups (Gazebo + Nav2): the cost under received paths; snapped Nav2
    A1C = 'docs/v2/r3/data/a1/costs_summary.json'
    a1 = j(A1C)['planners']

    def shares(name):
        return [s['share_of_plans_local_ge253'] for s in a1[name]['scenarios'].values()
                if s['share_of_plans_local_ge253'] is not None]
    th = shares('coco_user_theta_star')
    ctrl = shares('coco_user_astar_starter') + shares('stock')
    add('CostThetaMinPct', round(100 * min(th)), A1C)
    add('CostThetaMaxPct', round(100 * max(th)), A1C)
    add('CostControlMaxPct', round(100 * max(ctrl)), A1C)
    add('CostThetaReached', frac(a1['coco_user_theta_star']['reached'],
                                 a1['coco_user_theta_star']['goals']), A1C)
    add('CostStockReached', frac(a1['stock']['reached'], a1['stock']['goals']), A1C)
    add('CostAstarReached', frac(a1['coco_user_astar_starter']['reached'],
                                 a1['coco_user_astar_starter']['goals']), A1C)
    A1S = 'docs/v2/r3/data/a1/snap_summary.json'
    sv = j(A1S)['servers']
    add('SnapStockFound', frac(sv['compute_path_to_pose']['found'],
                               sv['compute_path_to_pose']['requests']), A1S)
    add('SnapSnappedFound', frac(sv['compute_path_to_pose+snapped']['found'],
                                 sv['compute_path_to_pose+snapped']['requests']), A1S)
    add('SnapAstarFound', frac(sv['user_compute_path_to_pose']['found'],
                               sv['user_compute_path_to_pose']['requests']), A1S)
    add('SnapMovedScenarios', len(sv['snap']['moved_scenarios']), A1S)
    add('SnapMaxGoalM', f(sv['snap']['goal_snap_m_max'], 2), A1S)
    add('SnapPairedGapM', f(sv['paired_snapped_minus_astar_starter_m']['median'], 3), A1S)
    add('SnapSessions', len(j(A1S)['sessions']), A1S)
    # COCO-Bench v1
    files = suites_v1()
    suites = [json.loads(p.read_text()) for p in files]
    src = 'coco_lab/coco_lab/benchmarks/*.v1.json'
    add('BenchSuites', len(suites), src)
    add('BenchScenarios', sum(len(x['scenarios']) for x in suites), src)
    fam = {}
    for x in suites:
        for fm in x['families']:
            fam.setdefault(fm, set()).add(x['id'])
    add('BenchPlanningSuites', len(fam.get('planning', ())), src)
    add('BenchControlSuites', len(fam.get('control', ())), src)
    add('BenchLocalisationSuites', len(fam.get('localisation', ())), src)
    add('BenchHeldOutTotal', sum(x['held_out']['n'] for x in suites), src)
    REP = 'docs/paper/generated/reproduce.json'
    add('ReproduceRuns', j(REP)['runs'], REP)
    add('BenchCarried', sum(1 for x in suites if x.get('from_v0')), src)
    depot = j('worlds/coco_depot_v1.json')
    b = depot['bounds']
    add('DepotWidthM', f"{b['x_max'] - b['x_min']:g}", 'worlds/coco_depot_v1.json')
    add('DepotHeightM', f"{b['y_max'] - b['y_min']:g}", 'worlds/coco_depot_v1.json')
    zones = [k for k in depot['kit'] if k.get('kind') == 'zone' and k.get('role') == 'region']
    add('DepotZones', len(zones), 'worlds/coco_depot_v1.json')
    add('DepotActors', sum(1 for k in depot['kit'] if k.get('kind') == 'actor'),
        'worlds/coco_depot_v1.json')
    sys.path.insert(0, str(REPO / 'coco_lab'))
    from coco_lab import bench_v1
    import math
    add('BendDeg', f'{math.degrees(bench_v1.BEND_RAD):g}', 'coco_lab/coco_lab/bench_v1.py')
    add('NarrowM', f'{bench_v1.NARROW_M:g}', 'coco_lab/coco_lab/bench_v1.py')
    add('ActorNearM', f'{bench_v1.ACTOR_NEAR_M:g}', 'coco_lab/coco_lab/bench_v1.py')
    clutter = j('worlds/coco_depot_clutter_v1.json')
    add('ClutterPallets', sum(1 for k in clutter['kit'] if k['id'].startswith('pallet_clutter_')),
        'worlds/coco_depot_clutter_v1.json')
    # R3.2: loc-global-20 at the teaching profile (MODEL), when its baseline is committed
    glob = 'docs/v2/r3/bench/loc-global-20/localisation/public'
    if (REPO / glob / 'runs.jsonl').is_file():
        spec = j(glob + '/spec.json')
        add('MclParticles', spec['algorithms'][0]['params']['mcl.particles'], glob + '/spec.json')
        gr = [json.loads(x) for x in (REPO / glob / 'runs.jsonl').read_text().splitlines()]
        add('GlobalSuccesses', sum(bool(r['success']) for r in gr), glob + '/runs.jsonl')
        add('GlobalRuns', len(gr), glob + '/runs.jsonl')
        add('GlobalConverged', sum(r['metrics']['converged_s'] is not None for r in gr), glob + '/runs.jsonl')
    # R3.2: task-fetch-10 (MODEL), when its baseline is committed
    fet = 'docs/v2/r3/bench/task-fetch-10/fulltask'
    if (REPO / fet / 'DONE').is_file():
        fr = [json.loads(x) for part in ('part1', 'part2')
              for x in (REPO / fet / part / 'runs.jsonl').read_text().splitlines()]
        add('FetchRuns', len(fr), fet)
        add('FetchCompleted', sum(bool(r['success']) for r in fr), fet)
        add('FetchPlanners', len({r['algorithm'] for r in fr}), fet)
        add('FetchContacts', sum(r['metrics']['contacts'] or 0 for r in fr), fet)
    # R3.2: loc-kidnap-20 (MODEL), when its baseline is committed
    kid = 'docs/v2/r3/bench/loc-kidnap-20/localisation/public/runs.jsonl'
    if (REPO / kid).is_file():
        kr = [json.loads(x) for x in (REPO / kid).read_text().splitlines()]
        add('KidnapRuns', len(kr), kid)
        add('KidnapSuccesses', sum(bool(r['success']) for r in kr), kid)
        add('KidnapRecovered', sum(r['metrics']['recovery_s'] is not None for r in kr), kid)
        add('KidnapBeliefArrivals', sum(bool(r['metrics']['reached_goal']) for r in kr), kid)
        ks = j('coco_lab/coco_lab/benchmarks/loc-kidnap-20.v1.json')['scenarios']
        km = sorted(s['features']['kidnap_m'] for s in ks)
        add('KidnapMinM', f'{km[0]:.1f}', 'coco_lab/coco_lab/benchmarks/loc-kidnap-20.v1.json')
        add('KidnapMaxM', f'{km[-1]:.1f}', 'coco_lab/coco_lab/benchmarks/loc-kidnap-20.v1.json')
        add('KidnapAtS', f"{ks[0]['kidnap_at_s']:g}", 'coco_lab/coco_lab/benchmarks/loc-kidnap-20.v1.json')
    # R3.2: ctrl-dynamic-30 split by the actor rule (MODEL), when its baseline is committed
    dyn = 'docs/v2/r3/bench/ctrl-dynamic-30/control/public/runs.jsonl'
    if (REPO / dyn).is_file():
        suite = j('coco_lab/coco_lab/benchmarks/ctrl-dynamic-30.v1.json')
        rule = {s['id']: ('Yield' if 'actors.yield=1' in s.get('config', []) else 'Walk')
                for s in suite['scenarios']}
        cnt = {}
        for line in (REPO / dyn).read_text().splitlines():
            r = json.loads(line)
            k = (r['algorithm'], rule[r['scenario']])
            c = cnt.setdefault(k, {'ok': 0, 'n': 0, 'timeout': 0, 'contact_ok': 0})
            c['n'] += 1
            c['ok'] += bool(r['success'])
            c['timeout'] += r['status'] == 'timeout'
            c['contact_ok'] += bool(r['success']) and (r['metrics']['contacts'] or 0) > 0
        name = {'builtin': 'Waypoint', 'dwa': 'Dwa', 'rpp': 'Rpp', 'mppi': 'Mppi'}
        for (algo, rl), c in sorted(cnt.items()):
            add(f'Dyn{name[algo]}{rl}', frac(c['ok'], c['n']), dyn)
        add('DynWaypointYieldTimeouts', cnt[('builtin', 'Yield')]['timeout'], dyn)
        add('DynWaypointWalkContactWins', cnt[('builtin', 'Walk')]['contact_ok'], dyn)
        add('DynWaypointWalkMaxContacts', max(
            (json.loads(x)['metrics']['contacts'] or 0) for x in (REPO / dyn).read_text().splitlines()
            if json.loads(x)['algorithm'] == 'builtin' and rule[json.loads(x)['scenario']] == 'Walk'), dyn)
    return out


def tex(ms):
    lines = ['% GENERATED by docs/paper/scripts/paper_numbers.py from committed data; never edit.',
             '% Each macro: its value, then the file it comes from.']
    for name, value, source in ms:
        lines.append(f'\\newcommand{{\\{name}}}{{{value}}} % {source}')
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    text = tex(macros())
    if a.check:
        same = OUT.is_file() and OUT.read_text() == text
        print('numbers.tex up to date' if same else 'numbers.tex DIFFERS from the data')
        return 0 if same else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f'{OUT.relative_to(REPO)}: {text.count(chr(10)) - 2} macros')
    return 0


if __name__ == '__main__':
    sys.exit(main())
