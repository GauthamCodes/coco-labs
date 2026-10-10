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
Learn missions (M2.8): load them, check their evidence, write their JSON.

A mission is DATA (``lab_web/missions/NN-<id>.yaml``): the seven beats --
hook, predict, reveal, manipulate, explain, check against the Stack,
challenge (a stub until M3) -- and the claims those beats make. Every
claim carries a learner-facing label and evidence references; this module
is the one place a reference is resolved, and the CI check
(``test_missions.py``) fails any claim whose evidence does not resolve.

A reference is one of:

- ``docs/RESULTS.md "<heading>"``: exactly one heading of docs/RESULTS.md
  begins with the quoted text (the form the v1 pages already cite);
- ``<path>::<name>``: a committed Python test file and a function in it;
- ``<path>``: a committed file.

``coverage()`` maps every claim the v1 Lab 1-5 pages showed
(docs/v2/data/m2/m28/v1_claims.json) to the mission claims that carry it;
``coverage_markdown()`` writes docs/v2/M2_CLAIMS_COVERAGE.md from it.
"""

import json
import os
import re
from typing import Dict, List, Tuple

import fidelity
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
MISSIONS = os.path.join(REPO, 'lab_web', 'missions')
V1_CLAIMS = os.path.join(REPO, 'docs', 'v2', 'data', 'm2', 'm28', 'v1_claims.json')
COVERAGE = os.path.join(REPO, 'docs', 'v2', 'M2_CLAIMS_COVERAGE.md')
#: M3.4: the Case Files a beat may open, and the moments it may open them at
CASEFILE_INDEX = os.path.join(REPO, 'lab_web', 'casefiles', 'index.json')
MOMENTS = os.path.join(REPO, 'docs', 'v2', 'data', 'm3', 'm34', 'moments.json')
MOMENT_KINDS = ('divergence', 'refusal')
BEATS = ('hook', 'predict', 'reveal', 'manipulate', 'explain', 'stack', 'challenge')
#: the learner-facing labels (CLAUDE.md "Evidence classes"); "TESTED": a
#: property test proves it; never REAL ROBOT RESULT -- no robot exists
LABELS = ('MEASURED', 'TESTED', 'SIMULATION RESULT', 'SIMPLIFIED MODEL', 'ASSUMPTION', 'INFERENCE', 'UNRESOLVED')
LENSES = ('plan', 'localise', 'map', 'move', 'decide')


class MissionError(ValueError):
    """A mission file that does not conform."""


def headings() -> List[str]:
    """Every heading of docs/RESULTS.md, without its #s."""
    with open(os.path.join(REPO, 'docs', 'RESULTS.md'), encoding='utf-8') as f:
        return [m.group(1).strip() for m in re.finditer(r'^#{1,6}\s+(.*)$', f.read(), re.M)]


def resolve(ref: str, heads: List[str]) -> str:
    """Return what ``ref`` resolves to, or raise :class:`MissionError`."""
    m = re.fullmatch(r'docs/RESULTS\.md "([^"]+)"', ref)
    if m:
        hits = [h for h in heads if h.startswith(m.group(1))]
        if len(hits) != 1:
            raise MissionError(f'{ref}: {len(hits)} headings begin with that text')
        return f'docs/RESULTS.md > {hits[0]}'
    path, _, name = ref.partition('::')
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', path) or '..' in path:
        raise MissionError(f'{ref}: not a reference this check reads')
    full = os.path.join(REPO, path)
    if not os.path.isfile(full):
        raise MissionError(f'{ref}: no such committed file')
    if name:
        with open(full, encoding='utf-8') as f:
            if not re.search(rf'^\s*def {re.escape(name)}\(', f.read(), re.M):
                raise MissionError(f'{ref}: no function {name} in {path}')
    return ref


def load() -> List[Dict[str, object]]:
    """Load every mission, in order, and check its shape."""
    out = []
    for name in sorted(os.listdir(MISSIONS)):
        if not name.endswith('.yaml'):
            continue
        with open(os.path.join(MISSIONS, name), encoding='utf-8') as f:
            m = yaml.safe_load(f)
        check(m, name)
        out.append(m)
    return out


def check(m: Dict[str, object], name: str) -> None:
    """Raise :class:`MissionError` unless ``m`` is a well-formed mission."""
    for key in ('schema', 'id', 'number', 'title', 'question', 'lens', 'v1', 'beats', 'claims'):
        if key not in m:
            raise MissionError(f'{name}: no {key}')
    if m['schema'] != 'coco.mission.v1':
        raise MissionError(f'{name}: schema must be coco.mission.v1')
    if m['lens'] not in LENSES:
        raise MissionError(f'{name}: lens {m["lens"]}')
    # M2.10: the v1 page is the frozen build at v1/ (docs/v2/adr/0003-v1-archive.md)
    if not str(m['v1']).startswith('v1/?view='):
        raise MissionError(f'{name}: v1 must link into the archive, v1/?view=...')
    for g in m.get('gaps', []):
        if g not in fidelity.GAP_IDS:
            raise MissionError(f'{name}: no model gap {g!r} (docs/v2/FIDELITY_v1.md has {fidelity.GAP_IDS})')
    beats = [b['beat'] for b in m['beats']]
    if tuple(beats) != BEATS:
        raise MissionError(f'{name}: the beats must be {BEATS}, in order (got {beats})')
    ids = set()
    for c in m['claims']:
        for key in ('id', 'text', 'label', 'evidence', 'v1'):
            if key not in c:
                raise MissionError(f'{name}: claim {c.get("id")} has no {key}')
        if c['id'] in ids:
            raise MissionError(f'{name}: duplicate claim {c["id"]}')
        ids.add(c['id'])
        if c['label'] not in LABELS:
            raise MissionError(f'{name}: claim {c["id"]}: label {c["label"]}')
        if not c['evidence']:
            raise MissionError(f'{name}: claim {c["id"]} cites nothing')
        # a heading with ': ' in it, unquoted, is a YAML mapping, not a string
        for ref in c['evidence'] + c['v1']:
            if not isinstance(ref, str):
                raise MissionError(f'{name}: claim {c["id"]}: {ref!r} is not a string (quote it)')
    used = set()
    for b in m['beats']:
        for cid in b.get('claims', []):
            if cid not in ids:
                raise MissionError(f'{name}: beat {b["beat"]} cites unknown claim {cid}')
            used.add(cid)
        if b['beat'] == 'predict':
            if not (b.get('options') and isinstance(b.get('answer'), int) and 0 <= b['answer'] < len(b['options'])):
                raise MissionError(f'{name}: predict needs options and an answer index')
        if b['beat'] == 'challenge' and not b.get('stub'):
            raise MissionError(f'{name}: the challenge beat is a stub until M3')
    if ids - used:
        raise MissionError(f'{name}: claims no beat shows: {sorted(ids - used)}')


def evidence_problems(missions) -> List[str]:
    """Every claim whose evidence does not resolve, as messages."""
    heads = headings()
    bad = []
    for m in missions:
        for c in m['claims']:
            for ref in c['evidence']:
                try:
                    resolve(ref, heads)
                except MissionError as e:
                    bad.append(f'{m["id"]}/{c["id"]}: {e}')
    return bad + casefile_link_problems(missions)


def casefile_link_problems(missions) -> List[str]:
    """
    Every beat link into a Case File that is not derived, as messages (M3.4).

    A ``casefile:`` link must name a committed Case File and a ``moment:``,
    and its ``tick:`` must be that moment's tick in the committed moments
    (docs/v2/data/m3/m34/moments.json, re-derived from the Case File by
    lab_web/test/casefile_moments.test.ts): a scrub target is never typed.
    """
    links = [(m['id'], b['beat'], b['arena']) for m in missions for b in m['beats']
             if (b.get('arena') or {}).get('casefile')]
    if not links:
        return []
    with open(CASEFILE_INDEX, encoding='utf-8') as f:
        have = {c['id'] for c in json.load(f)['casefiles']}
    with open(MOMENTS, encoding='utf-8') as f:
        moments = json.load(f)['casefiles']
    bad = []
    for mid, beat, a in links:
        where, cf, kind = f'{mid}/{beat}', a['casefile'], a.get('moment')
        if cf not in have:
            bad.append(f'{where}: no committed Case File {cf!r}')
        elif kind not in MOMENT_KINDS:
            bad.append(f'{where}: a Case File link names its moment, one of {MOMENT_KINDS}')
        elif not (moments.get(cf) or {}).get(kind):
            bad.append(f'{where}: {cf} has no {kind} moment in {os.path.relpath(MOMENTS, REPO)}')
        elif a.get('tick') != moments[cf][kind]['tick']:
            bad.append(f'{where}: tick {a.get("tick")!r} is not {cf}\'s {kind} moment, '
                       f'tick {moments[cf][kind]["tick"]}')
        if a.get('replay') or a.get('cfg'):
            bad.append(f'{where}: a Case File link opens the recording alone (no replay, no cfg)')
    return bad


def v1_claims() -> List[Dict[str, object]]:
    """Return the committed inventory of the v1 pages' claims."""
    with open(V1_CLAIMS, encoding='utf-8') as f:
        return json.load(f)['claims']


def coverage(missions) -> Tuple[Dict[str, List[Tuple[str, str, str]]], List[str], List[str]]:
    """Return (v1 id -> [(mission, claim, beat)], uncovered ids, unknown ids)."""
    known = {c['id'] for c in v1_claims()}
    where: Dict[str, List[Tuple[str, str, str]]] = {k: [] for k in known}
    unknown = []
    for m in missions:
        beat_of = {}
        for b in m['beats']:
            for cid in b.get('claims', []):
                beat_of.setdefault(cid, b['beat'])
        for c in m['claims']:
            for v in c['v1']:
                if v not in known:
                    unknown.append(f'{m["id"]}/{c["id"]}: {v}')
                else:
                    where[v].append((m['id'], c['id'], beat_of.get(c['id'], '')))
    return where, sorted(k for k, v in where.items() if not v), unknown


def coverage_markdown(missions) -> str:
    """Return the coverage table, docs/v2/M2_CLAIMS_COVERAGE.md."""
    where, uncovered, unknown = coverage(missions)
    claims = {c['id']: c for m in missions for c in m['claims']}
    v1 = v1_claims()
    by_lab: Dict[str, List[Dict[str, object]]] = {}
    for c in v1:
        by_lab.setdefault(c['lab'], []).append(c)
    lines = ['# M2 claims coverage: every v1 Lab 1-5 claim, in a Learn mission', '',
             'GENERATED by `lab_web/tools/missions.py` (`python3 lab_web/tools/missions.py --write`); '
             '`lab_web/tools/test_missions.py` fails if it is stale, if any v1 claim is not carried by some '
             "mission, or if any mission claim's evidence does not resolve.", '',
             f'The v1 inventory: `docs/v2/data/m2/m28/v1_claims.json` ({len(v1)} claims: every cited statement '
             "the v1 pages showed -- the site data's `cite`/`cites`/`citation` objects and every "
             '`className="cite"` element of the v1 views; made by `docs/v2/data/m2/m28/v1_claims.py`). '
             'M2.10 removed the v1 views from `main`: a `ui:<file>:<line>` id names that line as it stood at `1f91eee` (M2.8), '
             'where the inventory was made and can be re-made; the views themselves are served frozen at `v1/` '
             '(docs/v2/adr/0003-v1-archive.md).', '',
             f'**Covered: {len(v1) - len(uncovered)} of {len(v1)}.** Uncovered: {len(uncovered)}. '
             f'Unknown references: {len(unknown)}.', '']
    titles = {'lab1': 'Lab 1 (Plan)', 'lab2': 'Lab 2 (Localise)', 'lab3': 'Lab 3 (Map)', 'lab4': 'Lab 4 (Search)',
              'lab5': 'Lab 5 (Move)'}
    for lab in ('lab1', 'lab2', 'lab3', 'lab4', 'lab5'):
        lines += [f'## {titles[lab]}', '',
                  '| v1 claim | what it said | carried by (mission / claim / beat) | label | evidence |',
                  '|---|---|---|---|---|']
        for c in by_lab.get(lab, []):
            text = re.sub(r'\s+', ' ', str(c['text']))[:140].replace('|', '\\|')
            carriers = '; '.join(f'{m} / {cid} / {beat}' for m, cid, beat in where[c['id']]) or '**NOT COVERED**'
            labels = '; '.join(sorted({claims[cid]['label'] for _, cid, _ in where[c['id']]}))
            ev = '; '.join(sorted({e for _, cid, _ in where[c['id']] for e in claims[cid]['evidence']}))
            lines.append(f'| `{c["id"]}` | {text} | {carriers} | {labels} | {ev.replace("|", chr(92) + "|")} |')
        lines.append('')
    return '\n'.join(lines)


def site_json(missions) -> Dict[str, object]:
    """Return what the mission player reads (generated/missions.json)."""
    heads = headings()
    out = []
    for m in missions:
        mm = dict(m)
        mm['claims'] = [dict(c, resolved=[resolve(r, heads) for r in c['evidence']]) for c in m['claims']]
        out.append(mm)
    return {'schema': 'lab_web.missions', 'version': '1.0', 'missions': out}


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='write docs/v2/M2_CLAIMS_COVERAGE.md')
    a = ap.parse_args()
    ms = load()
    problems = evidence_problems(ms)
    for p in problems:
        print('EVIDENCE', p)
    _, unc, unk = coverage(ms)
    for u in unc:
        print('UNCOVERED', u)
    for u in unk:
        print('UNKNOWN', u)
    if a.write:
        with open(COVERAGE, 'w', encoding='utf-8') as f:
            f.write(coverage_markdown(ms) + '\n')
    print(f'{len(ms)} missions, {sum(len(m["claims"]) for m in ms)} claims, {len(problems)} evidence problems, '
          f'{len(unc)} uncovered, {len(unk)} unknown')
    # a problem is a failure here too, not only in build_catalog.py (M2 review, risk 6)
    raise SystemExit(1 if problems or unc or unk else 0)
