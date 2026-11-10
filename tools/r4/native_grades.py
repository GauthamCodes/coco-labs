#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R4.7: the native side of the browser/native grading agreement. Grades a fixed set of answers with
coco_lab.course natively and writes {case: {exercise, answer, passed, digest}}; the browser check
(lab_web/tools/r4/course_check.mjs) enters the same answers on the site and compares digests.

    python tools/r4/native_grades.py OUT.json
"""
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'coco_lab'))
os.environ.setdefault('COCO_WORLDS', str(REPO / 'worlds'))

from coco_lab import course as C  # noqa: E402

WRONG = REPO / 'coco_lab' / 'test' / 'course_wrong'


def cases():
    """The answers both sides grade: references, a wrong file, slider values, a tick."""
    out = {}
    for ex_id, lesson in (('m1-heuristic', 'write-the-heuristic'), ('m2-inflation', 'write-inflation'),
                          ('m5-resample', 'resampling'), ('m4-goal', 'goal-tolerance')):
        out[f'{ex_id}:reference'] = {'exercise': ex_id, 'lesson': lesson,
                                     'answer': {'code': C.file_text(C.exercise(ex_id)['solution'])}}
    out['m1-heuristic:three_octile'] = {'exercise': 'm1-heuristic', 'lesson': 'write-the-heuristic',
                                        'answer': {'code': (WRONG / 'm1_heuristic__three_octile.py').read_text()}}
    out['m2-inflation:rounded'] = {'exercise': 'm2-inflation', 'lesson': 'write-inflation',
                                   'answer': {'code': (WRONG / 'm2_inflation__rounded.py').read_text()}}
    out['m1-tune-weight:w3'] = {'exercise': 'm1-tune-weight', 'lesson': 'astar-vs-dijkstra',
                                'answer': {'params': {'heuristic_weight': 3.0}}}
    return out


def main() -> int:
    res = {}
    for k, c in cases().items():
        g = C.grade(c['exercise'], c['answer'])
        res[k] = dict(c, passed=g['passed'], digest=g['digest'])
        print(k, g['passed'], g['digest'][:16], flush=True)
    Path(sys.argv[1]).write_text(json.dumps(res, indent=1, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
