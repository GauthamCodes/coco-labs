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
Time the worker's glue (src/worker/recompute.py) under CPython.

The same edits the browser harness makes on the 0.10 m arena, run here so
the Pyodide numbers have a CPython reference on the same bundle. Needs
``build_catalog.py`` to have run (it reads public/generated/).

    python3 lab_web/tools/time_glue_cpython.py
"""

import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAB_WEB = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LAB_WEB, 'src', 'worker'))
import recompute  # noqa: E402

CELLS = [(95, 125), (98, 130), (91, 119), (96, 123), (97, 124), (93, 121)]


def main():
    d = os.path.join(LAB_WEB, 'public', 'generated', 'bundles', 'arena_0_10m')
    m = open(os.path.join(d, 'manifest.json'), 'rb').read()
    a = open(os.path.join(d, 'arrays.bin.gz'), 'rb').read()
    out = recompute.edit(m, 'arrays.bin.gz', a, *CELLS[0])
    first = out['timings']
    warm = []
    for cell in CELLS[1:]:
        out = recompute.edit(out['manifest'], out['arrays_name'], out['arrays_file'], *cell)
        warm.append(out['timings'])
    report = {
        'python': sys.version.split()[0],
        'loadavg': open('/proc/loadavg').read().split()[:3],
        'first_edit_ms': {k: round(v, 1) for k, v in first.items()},
        'warm_median_ms': {k: round(statistics.median(t[k] for t in warm), 1)
                           for k in first},
        'warm_edits': len(warm),
    }
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
