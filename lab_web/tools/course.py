# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R4 · the Learn course (``coco.lesson.v1``, ADR 0015): load the modules, check them, write their JSON.

A module is DATA (``lab_web/course/NN-<id>.yaml``): its lessons, each of the six steps --
predict, observe, explain, try, check, "In real ROS 2" -- and the claims they make. The
gradeable parts (questions, exercises, grading contracts) live in coco_lab
(``coco_lab/coco_lab/course/exercises.v1.json``) so the grader can run natively; a lesson
names them by id and this module refuses an id that does not exist.

Every claim carries a label and evidence references, resolved exactly as the missions' are
(:func:`missions.resolve`), plus ``docs/v2/r4/SOURCES.md > <id>`` for a checked primary
source. A claim may also reuse a mission's claim: ``mission:<mission id>/<claim id>``.
An explain text over :data:`MAX_EXPLAIN_WORDS` words is refused; so is an unmarked claim with
no evidence. Anything not yet verified must say ``[CHECK]`` in its text and is listed.

``site_json()`` adds what the page needs and Python computes: each run exercise's public
scenarios (from the exercise's seed, :func:`coco_lab.course.scenarios`), the starter and
solution files, so the page never re-derives them.
"""

import json
import os
import re
import sys
from typing import Dict, List

import missions
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
COURSE = os.path.join(REPO, 'lab_web', 'course')
SOURCES = os.path.join(REPO, 'docs', 'v2', 'r4', 'SOURCES.md')
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
os.environ.setdefault('COCO_WORLDS', os.path.join(REPO, 'worlds'))

SCHEMA = 'coco.lesson.v1'
TRACKS = ('explorer', 'builder', 'researcher')
STEPS = ('predict', 'observe', 'explain', 'try', 'ros2')
MAX_EXPLAIN_WORDS = 250
LABELS = missions.LABELS
#: the diagrams the page draws (lab_web/src/course/diagrams.tsx DIAGRAMS)
DIAGRAMS = ('search', 'inflation', 'replan', 'follow', 'particles', 'logodds', 'arbiter',
            'search-bays', 'timeline', 'ros-graph')


class CourseError(ValueError):
    """A course file that does not conform."""


def source_ids() -> List[str]:
    """The ids of docs/v2/r4/SOURCES.md's table (first column)."""
    with open(SOURCES, encoding='utf-8') as f:
        return re.findall(r'^\| ([a-z0-9-]+) \|', f.read(), re.M)


def resolve(ref: str, heads: List[str], sources: List[str]) -> str:
    """A claim's evidence reference, resolved (or :class:`CourseError`)."""
    m = re.fullmatch(r'docs/v2/r4/SOURCES\.md > ([a-z0-9-]+)', ref)
    if m:
        if m.group(1) not in sources:
            raise CourseError(f'{ref}: no such checked source')
        return ref
    try:
        return missions.resolve(ref, heads)
    except missions.MissionError as e:
        raise CourseError(str(e)) from None


def load() -> List[Dict]:
    """Every module, in order, checked."""
    out = []
    for name in sorted(os.listdir(COURSE)):
        if name.endswith('.yaml') and name[:2].isdigit():
            with open(os.path.join(COURSE, name), encoding='utf-8') as f:
                m = yaml.safe_load(f)
            check(m, name)
            out.append(m)
    nums = [m['number'] for m in out]
    if nums != list(range(1, len(out) + 1)):
        raise CourseError(f'module numbers {nums}: 1..n in file order')
    return out


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9*'.-]+", text))


def check(m: Dict, name: str) -> None:
    """Raise :class:`CourseError` unless ``m`` is a well-formed module."""
    from coco_lab import course as C
    for key in ('schema', 'id', 'number', 'title', 'question', 'lessons', 'claims'):
        if key not in m:
            raise CourseError(f'{name}: no {key}')
    if m['schema'] != SCHEMA:
        raise CourseError(f'{name}: schema {m["schema"]!r}')
    ex = C.exercises()
    ids = set()
    claim_ids = {c['id'] for c in m['claims']}
    for c in m['claims']:
        if c.get('label') not in LABELS:
            raise CourseError(f'{name}: claim {c["id"]}: label {c.get("label")!r}')
        if not c.get('evidence') and not c.get('mission') and '[CHECK]' not in c['text']:
            raise CourseError(f'{name}: claim {c["id"]} has no evidence and is not marked [CHECK]')
    for les in m['lessons']:
        lid = les.get('id', '?')
        if lid in ids:
            raise CourseError(f'{name}: duplicate lesson {lid}')
        ids.add(lid)
        if les.get('track') not in TRACKS:
            raise CourseError(f'{name}: {lid}: track {les.get("track")!r}')
        for step in STEPS:
            if step not in les:
                raise CourseError(f'{name}: {lid}: no {step} step')
        p = ex.get(les['predict'])
        if p is None or p['type'] != 'predict':
            raise CourseError(f'{name}: {lid}: predict {les["predict"]!r} is not a predict exercise')
        if les['try'] not in ex:
            raise CourseError(f'{name}: {lid}: try {les["try"]!r} is not an exercise')
        words = _words(les['explain']['text'])
        if words > MAX_EXPLAIN_WORDS:
            raise CourseError(f'{name}: {lid}: explain is {words} words (at most {MAX_EXPLAIN_WORDS})')
        if les['explain'].get('diagram') not in DIAGRAMS:
            raise CourseError(f'{name}: {lid}: diagram {les["explain"].get("diagram")!r}')
        for step in ('observe', 'explain', 'ros2'):
            for cid in les[step].get('claims', []):
                if cid not in claim_ids:
                    raise CourseError(f'{name}: {lid}: {step} cites unknown claim {cid}')
        r = les['ros2']
        if r.get('label') not in LABELS:
            raise CourseError(f'{name}: {lid}: ros2 label {r.get("label")!r}')
        if not r.get('claims'):
            raise CourseError(f'{name}: {lid}: "In real ROS 2" cites no claim')
        if les['observe'].get('arena'):
            missions_cfg = les['observe']['arena'].get('cfg', [])
            for c in missions_cfg:
                if not re.fullmatch(r'[a-z_]+(\.[a-z_]+)+=[A-Za-z0-9_.,+-]{1,64}', c):
                    raise CourseError(f'{name}: {lid}: arena cfg {c!r}')


def _mission_claims() -> Dict[str, Dict]:
    out = {}
    for ms in missions.load():
        for c in ms['claims']:
            out[f'{ms["id"]}/{c["id"]}'] = c
    return out


def evidence_problems(modules) -> List[str]:
    """Every claim whose evidence does not resolve (empty: all resolve)."""
    heads, sources, mc = missions.headings(), source_ids(), _mission_claims()
    bad = []
    for m in modules:
        for c in m['claims']:
            if c.get('mission') and c['mission'] not in mc:
                bad.append(f'{m["id"]}/{c["id"]}: no mission claim {c["mission"]}')
            for r in c.get('evidence', []):
                try:
                    resolve(r, heads, sources)
                except CourseError as e:
                    bad.append(f'{m["id"]}/{c["id"]}: {e}')
    return bad


def unverified(modules) -> List[str]:
    """Every claim or text still marked [CHECK] (listed in the report; never hidden)."""
    out = []
    for m in modules:
        for c in m['claims']:
            if '[CHECK]' in c['text']:
                out.append(f'{m["id"]}/{c["id"]}: {c["text"][:100]}')
        for les in m['lessons']:
            for step in ('observe', 'explain', 'ros2'):
                if '[CHECK]' in les[step].get('text', ''):
                    out.append(f'{m["id"]}/{les["id"]}/{step}')
    return out


def glossary() -> List[Dict]:
    """The glossary (lab_web/course/glossary.yaml), sorted, every term once."""
    with open(os.path.join(COURSE, 'glossary.yaml'), encoding='utf-8') as f:
        g = yaml.safe_load(f)
    terms = [t['term'] for t in g['terms']]
    if len(terms) != len({t.lower() for t in terms}):
        raise CourseError('glossary: a term twice')
    return sorted(g['terms'], key=lambda t: t['term'].lower())


def site_json(modules) -> Dict:
    """What the course page reads (generated/course.json)."""
    from coco_lab import course as C
    heads, sources, mc = missions.headings(), source_ids(), _mission_claims()
    ex = C.exercises()
    used = set()
    mods = []
    for m in modules:
        mm = dict(m)
        claims = []
        for c in m['claims']:
            cc = dict(c)
            if c.get('mission'):
                base = mc[c['mission']]
                cc = dict(base, **{k: v for k, v in c.items()
                                   if k != 'mission' and v not in ('', None)})
                cc.setdefault('evidence', base['evidence'])
            cc['resolved'] = [resolve(r, heads, sources) for r in cc.get('evidence', [])]
            cc.pop('v1', None)
            claims.append(cc)
        mm['claims'] = claims
        for les in m['lessons']:
            used.update([les['predict'], les['try']])
        mods.append(mm)
    exercises = {}
    for eid in sorted(used):
        e = dict(ex[eid])
        if e['type'] in ('code', 'benchmark'):
            e['starter_code'] = C.file_text(e['starter'])
            e['solution_code'] = C.file_text(e['solution'])
        if e['type'] in ('code', 'benchmark', 'tune') and 'scenarios' in e:
            e['public_scenarios'] = C.scenarios(e, 'public')
        if e['type'] == 'failure':
            e['timeline'] = C.inspect(eid)
        exercises[eid] = e
    return {'schema': SCHEMA, 'version': 1, 'modules': mods, 'exercises': exercises,
            'glossary': glossary(), 'max_explain_words': MAX_EXPLAIN_WORDS}


if __name__ == '__main__':
    ms = load()
    problems = evidence_problems(ms)
    for p in problems:
        print('EVIDENCE', p)
    for u in unverified(ms):
        print('[CHECK]', u)
    n_less = sum(len(m['lessons']) for m in ms)
    print(f'{len(ms)} modules, {n_less} lessons, {sum(len(m["claims"]) for m in ms)} claims, '
          f'{len(problems)} evidence problems, {len(unverified(ms))} [CHECK]')
    if '--write' in sys.argv:
        out = sys.argv[sys.argv.index('--write') + 1]
        with open(out, 'w', encoding='utf-8') as f:
            f.write(json.dumps(site_json(ms), indent=1, sort_keys=True) + '\n')
    raise SystemExit(1 if problems else 0)
