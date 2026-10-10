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
The Case Files' text, checked; the site's casefiles.json (M3.3).

    python3 lab_web/tools/casefiles.py            check; exit 1 on any problem

Reads ``lab_web/casefiles/cases.yaml`` (the text) and
``lab_web/casefiles/index.json`` (what was converted and packed). The
EVIDENCE CHECK, extended from the Learn missions (``missions.py``) to Case
Files: every explanation sentence carries a learner label and evidence that
resolves (a RESULTS.md heading matched exactly once, a committed file, or a
test function that exists); every unresolved question is labelled
UNRESOLVED and cites evidence; every RESULTS link resolves. Then the
inventory: every recording the committed data names has a packed Case File
(Lab 4: the manifest's 16 runs plus the void; Lab 5: the drive manifests'
54; Lab 1C: the three runs; Lab 2: the kidnap record's sessions), each
within the ADR 0005 budget. Per-run facts are generated here from that
committed data, each citing the file it came from. ``build_catalog.py``
runs this and refuses to build on a problem; ``test_casefiles.py`` too.
"""

import json
import os
import re
import sys
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import missions  # noqa: E402

REPO = missions.REPO
CASES = os.path.join(REPO, 'lab_web', 'casefiles', 'cases.yaml')
INDEX = os.path.join(REPO, 'lab_web', 'casefiles', 'index.json')
LABELS = missions.LABELS
PER_FILE_BUDGET = 20_000_000
TOTAL_BUDGET = 150_000_000
GAP_IDS = ('lidar', 'odometry', 'tracking')


class CaseFileError(ValueError):
    """A Case File the site must not show."""


def load():
    import yaml
    with open(CASES, encoding='utf-8') as f:
        doc = yaml.safe_load(f)
    with open(INDEX, encoding='utf-8') as f:
        index = json.load(f)
    return doc, index


def _data(rel):
    with open(os.path.join(REPO, rel), encoding='utf-8') as f:
        return json.load(f)


# -- the text -----------------------------------------------------------------------

def text_problems(doc) -> List[str]:
    heads = missions.headings()
    out = []
    ids = set()
    for g in doc['groups']:
        gid = g.get('id', '?')
        if gid in ids:
            out.append(f'{gid}: two groups share this id')
        ids.add(gid)
        if not g.get('explain'):
            out.append(f'{gid}: no explanation')
        for i, s in enumerate(g.get('explain', [])):
            if s.get('label') not in LABELS:
                out.append(f'{gid}: explain[{i}] label {s.get("label")!r} is not a learner label')
            if not str(s.get('text', '')).strip():
                out.append(f'{gid}: explain[{i}] has no text')
            if not s.get('evidence'):
                out.append(f'{gid}: explain[{i}] cites nothing')
            for r in s.get('evidence', []):
                try:
                    missions.resolve(r, heads)
                except missions.MissionError as e:
                    out.append(f'{gid}: explain[{i}]: {e}')
        for i, u in enumerate(g.get('unresolved', [])):
            if u.get('label', 'UNRESOLVED') != 'UNRESOLVED':
                out.append(f'{gid}: unresolved[{i}] must stay labelled UNRESOLVED')
            if not u.get('evidence'):
                out.append(f'{gid}: unresolved[{i}] cites nothing')
            for r in u.get('evidence', []):
                try:
                    missions.resolve(r, heads)
                except missions.MissionError as e:
                    out.append(f'{gid}: unresolved[{i}]: {e}')
        if not g.get('results'):
            out.append(f'{gid}: no link to docs/RESULTS.md')
        for r in g.get('results', []):
            if not r.startswith('docs/RESULTS.md'):
                out.append(f'{gid}: results link {r!r} is not into docs/RESULTS.md')
            try:
                missions.resolve(r, heads)
            except missions.MissionError as e:
                out.append(f'{gid}: results: {e}')
        for rel in list(g.get('data', [])) + [g.get('facts')] + [g.get('backends')]:
            if rel and not os.path.exists(os.path.join(REPO, rel)):
                out.append(f'{gid}: no committed {rel}')
        for gap in g.get('gaps', []):
            if gap not in GAP_IDS:
                out.append(f'{gid}: unknown model gap {gap!r}')
    return out


# -- the inventory -------------------------------------------------------------------

def expected(doc) -> Dict[str, List[str]]:
    """Case File ids each converted group must have, from committed data alone."""
    out = {}
    for g in doc['groups']:
        src = g['source']
        k = src['kind']
        if k == 'lab1c':
            out[g['id']] = [f'lab1_{r}' for r in src['runs']]
        elif k == 'lab4':
            ids = ['lab4_' + r['id'].lower() for r in _data(src['manifest'])['runs']]
            ids += ['lab4_' + re.sub(r'[^a-z0-9]+', '_', v.lower()).strip('_') for v in src.get('void', [])]
            out[g['id']] = ids
        elif k == 'lab5':
            ids = []
            root = os.path.join(REPO, src['manifests'])
            for sc in sorted(os.listdir(root)):
                p = os.path.join(src['manifests'], sc, 'manifest.json')
                if os.path.isfile(os.path.join(REPO, p)):
                    ids += ['lab5_' + r['record']['run'].lower() for r in _data(p)['runs']]
            out[g['id']] = ids
        elif k == 'lab2_kidnap':
            out[g['id']] = None   # the sessions are directories of the runs root: checked by count below
        elif k == 'multi':
            out[g['id']] = [c['id'] for c in src['cases']]
    return out


def inventory_problems(doc, index) -> List[str]:
    out = []
    by_group: Dict[str, List[dict]] = {}
    for e in index['casefiles']:
        by_group.setdefault(e['group'], []).append(e)
        if e['bytes'] > PER_FILE_BUDGET:
            out.append(f"{e['id']}: {e['bytes']} B is over the per-file budget")
        if not os.path.isfile(os.path.join(REPO, 'lab_web', 'casefiles', e['id'] + '.mcap')):
            out.append(f"{e['id']}: listed but no lab_web/casefiles/{e['id']}.mcap")
        if not e.get('bags'):
            out.append(f"{e['id']}: cites no source bag")
    total = sum(e['bytes'] for e in index['casefiles'])
    if total > TOTAL_BUDGET:
        out.append(f'the Case Files total {total} B, over the budget')
    groups = {g['id'] for g in doc['groups']}
    for gid in by_group:
        if gid not in groups:
            out.append(f'{gid}: packed Case Files of a group cases.yaml does not have')
    for gid, ids in expected(doc).items():
        have = sorted(e['id'] for e in by_group.get(gid, []))
        if ids is None:
            sessions = _data('docs/data/lab2/kidnap_ab.json')['trials']
            if len(have) != len(sessions):
                out.append(f'{gid}: {len(have)} Case Files for {len(sessions)} recorded sessions')
        elif sorted(ids) != have:
            out.append(f'{gid}: missing {sorted(set(ids) - set(have))}, extra {sorted(set(have) - set(ids))}')
    return out


# -- per-run facts, from committed data ------------------------------------------------

def _num(v, unit='', nd=3):
    return '—' if v is None else f'{v:.{nd}f}{unit}'


def facts(doc, entry) -> List[dict]:
    """Sentences about one recording, generated from the committed data that holds them."""
    c = entry['case']
    lab = c.get('lab')
    if lab == 4 and not c.get('void'):
        src = 'docs/data/lab4/replay/p05_matrix/manifest.json'
        r = next(x for x in _data(src)['runs'] if x['id'] == c['run'])
        rec, s = r['record'], r['summary']
        out = [f"Told to fetch the {rec['colour']} target; it looked in {', '.join(s['order'][:s['surveys']])}."]
        found = s.get('discovered')
        out.append(f"Found it in {found} (look {s['discovered_at']})." if found else 'It did not find the target.')
        tail = f"Mission {rec['outcome']}" + (f" ({rec['reason']})" if rec.get('reason') else '')
        if rec.get('home_error_m') is not None:
            tail += f"; home error {rec['home_error_m']:.3f} m"
        tail += f"; {rec['relocalisations']} relocalisation(s), {rec['recoveries']} recover(ies)."
        out.append(tail)
        return [{'label': 'SIMULATION RESULT', 'text': t, 'evidence': [src]} for t in out]
    if lab == 4 and c.get('void'):
        return [{'label': 'SIMULATION RESULT', 'text': 'VOID: not counted. The harness could not join its DDS '
                 'domain (earlier recorders had outlived their runs); the run was repeated.',
                 'evidence': ['docs/RESULTS.md "The searching mission in Gazebo"']}]
    if lab == 5:
        src = f"docs/data/lab5/drive/{c['scenario']}/manifest.json"
        r = next(x for x in _data(src)['runs'] if x['record']['run'] == c['run'])
        m = r.get('metrics') or {}
        code = r['record'].get('error_code')
        out = [f"{r['controller']} on {c['scenario']}: {r['outcome']}" + (f' (error code {code})' if code else '') + '.']
        tr = (m.get('tracking_m') or {})
        cl = (m.get('clearance') or {})
        if tr:
            out.append(f"Tracking error from the frozen path: mean {_num(tr.get('mean'), ' m')}, max {_num(tr.get('max'), ' m')}.")
        if cl:
            out.append(f"Minimum clearance {_num(cl.get('min_m'), ' m')}" + (' (contact)' if cl.get('contact') else '') + '.')
        return [{'label': 'SIMULATION RESULT', 'text': t, 'evidence': [src]} for t in out]
    if lab == 2 and c.get('session'):
        src = 'docs/data/lab2/kidnap_ab.json'
        trials = [t for t in _data(src)['trials'] if t['session'] == c['session']]
        if c.get('void') or not trials:
            why = trials[0]['void'] if trials and trials[0].get('void') else 'see the kidnap record'
            return [{'label': 'SIMULATION RESULT', 'text': f'VOID: not counted ({why}).',
                     'evidence': ['docs/RESULTS.md "The kidnap A/B on the real stack"']}]
        t = trials[0]
        arm = 'injection on' if t['arm'] == 'recovery' else 'as shipped (no injection)'
        out = [f"Arm: {arm}; kidnapped to {t['target']} {tuple(t['to_map'])}."]
        out.append(f"Recovered after {t['recovery_s']:.1f} s." if t['recovered']
                   else f"Not recovered in {t['duration_s']:.0f} s; ended {t['err_xy'][-1]:.1f} m from the truth.")
        return [{'label': 'SIMULATION RESULT', 'text': x, 'evidence': [src]} for x in out]
    if lab == 1:
        src = 'docs/data/lab1c/runs.json'
        r = next(x for x in _data(src)['runs'] if os.path.basename(x['dir']) == c['run'])
        phase = (r.get('live_checks') or {}).get('end', {}).get('lab_phase', '?')
        return [{'label': 'SIMULATION RESULT', 'text': f"{c['run'][4:]}: the lab's final phase was {phase}.",
                 'evidence': [src]}]
    return []


def compare_url(group, entry) -> str:
    """The Arena model's side of the comparison, as a URL query (the model, labelled MODEL)."""
    p = group.get('compare', {}).get('params', {})
    q = ['view=arena']
    if p.get('lens'):
        q.append(f"lens={p['lens']}")
    cfg = list(p.get('cfg', []))
    c = entry['case'] if entry else {}
    if entry and group.get('compare', {}).get('per_run_cfg_from') == 'move':
        ctl = {'DWB': 'dwa', 'MPPI': 'mppi', 'RPP': 'rpp'}[c['controller']]
        cfg += [f'move.controller={ctl}', f"move.scenario={c['scenario']}"]
    if entry and group.get('compare', {}).get('per_run_cfg_from') == 'fetch' and not c.get('void'):
        r = next(x for x in _data(group['facts'])['runs'] if x['id'] == c['run'])
        truth = (r.get('evaluator') or {}).get('truth_region')
        if truth:
            cfg.append(f'mission.truth={truth}')
        cfg.append(f"mission.start={r['record']['colour']}")
    q += [f'cfg={x}' for x in cfg]
    if entry and group.get('compare', {}).get('per_run_kidnap_from') and c.get('session'):
        trials = [t for t in _data('docs/data/lab2/kidnap_ab.json')['trials'] if t['session'] == c['session']]
        if trials and trials[0].get('to_map'):
            x, y, th = trials[0]['to_map']
            q.append(f'kidnap={x},{y},{th}')
    if entry and group.get('compare', {}).get('per_run_goal_from') and lab_goal(c):
        q.append('goal=' + ','.join(str(v) for v in lab_goal(c)))
    return '?' + '&'.join(q)


def lab_goal(c):
    if c.get('lab') != 1:
        return None
    r = next(x for x in _data('docs/data/lab1c/runs.json')['runs'] if os.path.basename(x['dir']) == c['run'])
    g = (r.get('meta') or {}).get('goal_map')
    return g[:2] if g else None


def site_json(doc, index) -> Dict[str, object]:
    heads = missions.headings()
    entries = {e['id']: e for e in index['casefiles']}
    groups = []
    for g in doc['groups']:
        gg = {k: g[k] for k in ('id', 'title', 'lab', 'gaps', 'results') if k in g}
        gg['results_resolved'] = [missions.resolve(r, heads) for r in g['results']]
        gg['explain'] = [dict(s, resolved=[missions.resolve(r, heads) for r in s['evidence']]) for s in g['explain']]
        gg['unresolved'] = [dict(u, label='UNRESOLVED', resolved=[missions.resolve(r, heads) for r in u['evidence']])
                            for u in g.get('unresolved', [])]
        gg['compare'] = {'what': g.get('compare', {}).get('what', ''), 'url': compare_url(g, None)}
        src = g['source']
        if src['kind'] == 'group':
            if 'cases' in src:
                ids = src['cases']
            else:
                sel = src['select']
                ids = [e['id'] for e in index['casefiles'] if e['group'] == sel['group']
                       and all(e['case'].get(k) == v for k, v in sel.items() if k != 'group')]
            gg['members'] = ids
            gg['casefiles'] = []
        else:
            gg['casefiles'] = []
            for e in index['casefiles']:
                if e['group'] != g['id']:
                    continue
                gg['casefiles'].append({
                    'id': e['id'], 'title': e['title'], 'file': f"generated/casefiles/{e['id']}.mcap",
                    'bytes': e['bytes'], 'sha256': e['sha256'], 'run_id': e['run_id'], 'bags': e['bags'],
                    'checksum': e['checksum'], 'void': bool(e['case'].get('void')),
                    'facts': facts(doc, e), 'compare': compare_url(g, e)})
        if g.get('backends'):
            gg['backends'] = backends(g['backends'])
        groups.append(gg)
    return {'schema': 'lab_web.casefiles', 'version': '1.0', 'groups': groups,
            'total_bytes': index['total_bytes']}


def backends(rel) -> List[dict]:
    """Lab 3's backend runs: ATE and F1 per backend, drive and loop closure, as results.json holds them."""
    d = _data(rel)
    out = []
    for b in sorted(d.get('backends', []), key=lambda b: (b['drive'], b['backend'], b['arm'], b['round'])):
        out.append({'backend': b['backend'], 'drive': b['drive'],
                    'loop closure': 'on' if b['arm'] == 'loop' else 'off', 'round': b['round'],
                    'map F1': round(b['f1'], 3), 'ATE RMSE (m)': round(b['ate_online_rmse'], 3)})
    return out


def problems():
    doc, index = load()
    return text_problems(doc) + inventory_problems(doc, index)


if __name__ == '__main__':
    ps = problems()
    for p in ps:
        print('CASEFILE', p)
    doc, index = load()
    print(f"{len(doc['groups'])} groups, {len(index['casefiles'])} Case Files, "
          f"{index['total_bytes']:,} B, {len(ps)} problems")
    sys.exit(1 if ps else 0)
