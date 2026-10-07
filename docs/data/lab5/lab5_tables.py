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
Print Phase 6's results tables as Markdown, from results.json. No ROS.

  python3 docs/data/lab5/lab5_tables.py [results.json]

The tables in docs/labs/LAB5_MOVE.md and docs/RESULTS.md "COCO Lab Phase
6" are this script's output, pasted, so no number in them is typed by hand.
Medians over runs with [min - max]; three decimals for metres, one for
seconds, two for accelerations (display rounding only).
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def d(x, k):
    if x is None or x.get('median') is None:
        return '—'
    return f"{x['median']:.{k}f} [{x['min']:.{k}f}–{x['max']:.{k}f}]"


def outcomes(r):
    parts = [f'{n} {o}' for o, n in sorted(r['outcomes'].items())]
    codes = f" (code {', '.join(map(str, r['error_codes']))})" \
        if r['error_codes'] else ''
    return ', '.join(parts) + codes


def main(path):
    R = json.load(open(path))
    for sc, b in R['scenarios'].items():
        print(f'\n#### {sc} — {b["title"]}\n')
        print(f'Path `{b["path_sha256"][:12]}…`, drive bundle '
              f'`{b["content_hash"][:19]}…`.\n')
        print('| controller | runs | outcome | tracking mean (m) | tracking '
              'max (m) | time, reached (s) | RMS dv/dt (m/s²) | RMS dw/dt '
              '(rad/s²) | min clearance (m) | contacts in window / whole '
              'recording |')
        print('|---|---|---|---|---|---|---|---|---|---|')
        for c, r in b['controllers'].items():
            print(f"| {c} | {r['runs']} | {outcomes(r)} | "
                  f"{d(r['tracking_mean_m'], 3)} | {d(r['tracking_max_m'], 3)}"
                  f" | {d(r['time_s_succeeded'], 1)} | "
                  f"{d(r['rms_linear_accel'], 2)} | "
                  f"{d(r['rms_angular_accel'], 2)} | "
                  f"{d(r['min_clearance_m'], 3)} | {r['contacts']} / "
                  f"{r['actor_contacts_whole_recording']} |")
    print(f"\nVoid attempts: {len(R['void'])}.")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1
                  else os.path.join(HERE, 'results.json')))
