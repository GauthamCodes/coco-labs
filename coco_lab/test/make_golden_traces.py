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
Freeze Lab 1's traces on the 1,000-map property corpus (M1.4).

    cd coco_lab && python3 test/make_golden_traces.py OUT.json.gz

Run ONCE, on the v1 search implementation, before M1.4 changed
``coco_lab/search.py``; its output is committed as
``coco_lab/test/golden_traces_v1.json.gz`` and ``test_golden_traces.py``
checks the event API against it in CI.

The corpus is the one property that runs all five algorithms on the same
map: ``test_properties.test_all_five_agree_on_no_path`` (derandomized,
1,000 examples, half the maps walled). This runs that test itself, with
``lab_maps.CASE_LOG`` recording each drawn map's parameters and a wrapper
around ``search`` recording every call: its arguments, status, expansions,
cost and the sha256 of the trace's canonical JSON (``Trace.to_json``), which
pins the whole trace -- every event in order, every g, h and f, every
parent, the path, the summary.
"""

import gzip
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from coco_lab import search as search_mod  # noqa: E402
import lab_maps  # noqa: E402
import test_properties  # noqa: E402


def main(out):
    """Run the corpus and write the golden file."""
    calls = []
    real = search_mod.search

    def recording(graph, start, goal, algorithm, **kw):
        r = real(graph, start, goal, algorithm, **kw)
        calls.append({
            'start': list(start), 'goal': list(goal),
            'algorithm': algorithm, 'heuristic': kw.get('heuristic', 'zero'),
            'tie_break': kw.get('tie_break', 'low_h'),
            'weight': kw.get('weight'),
            'status': r.status,
            'expansions': r.trace.summary['expansions'],
            'events': len(r.trace),
            'cost': r.cost,
            'trace_sha256': hashlib.sha256(
                r.trace.to_json().encode('utf-8')).hexdigest(),
        })
        return r

    lab_maps.CASE_LOG = []
    test_properties.search = recording
    try:
        test_properties.test_all_five_agree_on_no_path()
    finally:
        test_properties.search = real
    params = lab_maps.CASE_LOG
    lab_maps.CASE_LOG = None
    if len(calls) != 5 * len(params):
        raise SystemExit(f'{len(calls)} searches for {len(params)} maps')
    cases = []
    for i, p in enumerate(params):
        runs = calls[5 * i:5 * i + 5]
        assert len({(r['start'][0], r['start'][1], r['goal'][0],
                     r['goal'][1]) for r in runs}) == 1
        cases.append({'params': p, 'start': runs[0]['start'],
                      'goal': runs[0]['goal'],
                      'runs': [{k: v for k, v in r.items()
                                if k not in ('start', 'goal')}
                               for r in runs]})
    sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=HERE,
                         capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(['git', 'status', '--porcelain', '--',
                                 os.path.join(HERE, '..', 'coco_lab')],
                                cwd=HERE, capture_output=True,
                                text=True).stdout.strip())
    doc = {
        'what': "Lab 1's v1 search traces on the 1,000-map property corpus",
        'corpus': 'coco_lab/test/test_properties.py::'
                  'test_all_five_agree_on_no_path (derandomized)',
        'maps': len(cases), 'searches': len(calls),
        'source_commit': sha, 'coco_lab_dirty': dirty,
        'digest': 'sha256 of coco_lab.trace.Trace.to_json() (canonical JSON)',
        'rebuild': 'lab_maps.build_case(**params)',
        'cases': cases,
    }
    with gzip.open(out, 'wt', encoding='utf-8', compresslevel=9) as f:
        f.write(json.dumps(doc, sort_keys=True, separators=(',', ':')))
    found = sum(r['status'] == 'found' for r in calls)
    print(f'{len(cases)} maps, {len(calls)} searches ({found} found), '
          f'commit {sha[:7]}{" DIRTY" if dirty else ""} -> {out}')


if __name__ == '__main__':
    main(sys.argv[1])
