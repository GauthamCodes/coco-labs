# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""M0 fix A.3: search the site source and the non-archived docs for hardware
wording, and classify every hit.

    python3 docs/v2/data/m0/copycheck_text.py [RENDERED_JSON] > OUT.json

Terms: "real robot", "two-finger", "2-finger", "magnet gripper".
Scope: lab_web/src, docs/ (minus docs/archive/), README.md, CLAUDE.md,
PROJECT_STATE.md. A hit is acceptable only if it is classified below; any
other hit is reported as ``needs_fix`` and the exit status is 1.
RENDERED_JSON, if given, is lab_web/tools/perf/copycheck.mjs output (what a
visitor sees on screen) and is embedded as is.
"""

import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
TERMS = re.compile(r'real robot|two-finger|2-finger|magnet gripper', re.I)
SCOPE = ['lab_web/src', 'docs', 'README.md', 'CLAUDE.md', 'PROJECT_STATE.md']
HEADER = re.compile(r'^> \*\*Correction \(2026-10-08')

# (path, substring of the line) -> (class, reason). Substrings, not line
# numbers, so an append elsewhere in a file does not invalidate the table.
KNOWN = [
    ('README.md', 'real robotics metrics', 'not_hardware', '"real robotics metrics" is not a robot claim'),
    ('README.md', 'REAL ROBOT RESULT', 'label_vocabulary', 'the evidence-label name for HARDWARE results (none exist)'),
    ('README.md', 'say "the full ROS 2 stack (simulated)"', 'correction_rule', 'the plan\'s own correction rule'),
    ('README.md', 'no "real robot" wording anywhere', 'correction_rule', 'decision G5 default'),
    ('CLAUDE.md', 'REAL ROBOT RESULT', 'label_vocabulary', 'the label name, followed by "No physical robot exists"'),
    ('PROJECT_STATE.md', 'until 2026-10-08 this read', 'quotes_old_text', 'records the M0.6 rewording'),
    ('docs/STATUS.md', '', 'status_record', 'STATUS.md records the corrections themselves'),
    ('docs/IDEAS.md', '', 'idea_log', 'parked ideas quoting the wording to replace'),
    ('docs/live/LIVE.md', 'Until 2026-10-08 this title read', 'quotes_old_text', 'records the M0.6 retitle'),
    ('docs/labs/LAB3_MAP.md', 'A real robot.', 'negation', 'listed under "Not verified"; the line says it ran on the stack'),
    ('docs/history/ROADMAP_COCO2.md', 'COCO stays a real robotics', 'not_hardware', '"real robotics project", not a robot claim'),
    ('docs/SESSION_LOG.md', 'bounds what C2-M2.1 can claim', 'hypothetical', 'what a noiseless sim IMU cannot say about hardware'),
    ('docs/SESSION_LOG.md', 'still bounds what any of it claims about a real robot', 'hypothetical', 'same'),
    ('docs/SESSION_LOG.md', 'real robot.', 'hypothetical',
     'wrapped tail of "it bounds what C2-M2.1 can claim about a real robot" (line 1750-1751)'),
    ('docs/SESSION_LOG.md', 'no "real robot" for the Gazebo', 'status_record', 'the M0.6 log entry'),
    ('docs/RESULTS.md', 'that role on a real robot is an open question', 'hypothetical', 'an open question about hardware'),
    ('docs/RESULTS.md', 'The real robot chose what coco_lab chooses', 'covered_by_appended_note',
     'append-only correction note at the end of RESULTS.md (M0 fix A.3)'),
    ('docs/RESULTS.md', '"real robot" in Phase 5', 'correction_text', 'the appended note'),
    ('docs/RESULTS.md', 'line 8568 reads', 'correction_text', 'the appended note'),
    ('docs/RESULTS.md', 'chooses"**. There, "real robot" means', 'correction_text', 'the appended note'),
    ('docs/v2/data/m0/', '', 'evidence_record', 'M0 evidence quoting the wording it checked'),
]


def files():
    for s in SCOPE:
        p = os.path.join(ROOT, s)
        if os.path.isfile(p):
            yield s
            continue
        for d, dirs, names in os.walk(p):
            rel = os.path.relpath(d, ROOT)
            if rel.startswith(os.path.join('docs', 'archive')):
                dirs[:] = []
                continue
            for n in sorted(names):
                if n.endswith(('.md', '.ts', '.tsx', '.json', '.py', '.txt', '.html')):
                    yield os.path.join(rel, n)


def classify(path, text, line, has_header):
    if has_header and HEADER.match(line):
        return 'correction_text', 'the file\'s correction header'
    for p, sub, cls, why in KNOWN:
        if (path == p or (p.endswith('/') and path.startswith(p))) and sub in line:
            return cls, why
    if has_header:
        return 'covered_by_header', 'the file opens with a 2026-10-08 correction header'
    return 'needs_fix', 'present-tense hardware wording with no correction'


def main():
    hits = []
    for path in sorted(set(files())):
        with open(os.path.join(ROOT, path), encoding='utf-8') as f:
            lines = f.read().split('\n')
        has_header = any(HEADER.match(x) for x in lines[:12])
        for i, line in enumerate(lines, 1):
            m = TERMS.search(line)
            if not m:
                continue
            cls, why = classify(path, line, line, has_header)
            hits.append({'file': path, 'line': i, 'term': m.group(0), 'text': line.strip()[:200],
                         'class': cls, 'why': why})
    head = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    counts = {}
    for h in hits:
        counts[h['class']] = counts.get(h['class'], 0) + 1
    out = {'terms': TERMS.pattern, 'scope': SCOPE, 'excluded': ['docs/archive/'], 'commit_before_this_file': head,
           'hits': len(hits), 'by_class': counts, 'needs_fix': [h for h in hits if h['class'] == 'needs_fix'],
           'detail': hits}
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding='utf-8') as f:
            out['rendered_site'] = json.load(f)
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    sys.stdout.write('\n')
    return 1 if out['needs_fix'] else 0


if __name__ == '__main__':
    sys.exit(main())
