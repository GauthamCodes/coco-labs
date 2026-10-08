"""M0.2: do the recordings docs/RESULTS.md cites by checksum resolve?

Read-only. Re-implements coco_lab_ros.export.dir_sha256 (sorted
"relpath sha256" lines, hashed) so no ROS import is needed.
Usage: python3 -I check_recordings.py
"""
import hashlib
import json
import os

RUNS = os.path.expanduser('~/coco_lab_runs')

# docs/RESULTS.md lines 7078-7080 ("Evidence per run", COCO Lab Phase 1C).
CITED = [
    ('lab1c/run_astar/bag',
     '13bc214dc78c2f3c761ca84d64a85c7fe4f5243d56b6546ad495536995a96c4f', 8127558),
    ('lab1c/run_dijkstra/bag',
     '498253a12e277ebfe16934fc11e74dbe305a8abf1ff4bcd35664a506b6c771dc', 8402694),
    ('lab1c/run_greedy/bag',
     '82b76311ee0d3ff9391f3f62cbc34bc5f7ea95e532bd814794d101870f847b7b', 6891474),
]


def file_sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def dir_sha256(root):
    lines, size = [], 0
    for dirpath, _, files in os.walk(root):
        for name in files:
            p = os.path.join(dirpath, name)
            lines.append(f'{os.path.relpath(p, root)} {file_sha256(p)}\n')
            size += os.path.getsize(p)
    return hashlib.sha256(''.join(sorted(lines)).encode()).hexdigest(), size


out = []
for rel, want, want_size in CITED:
    path = os.path.join(RUNS, rel)
    if not os.path.isdir(path):
        out.append({'path': rel, 'resolves': False, 'reason': 'missing'})
        continue
    got, size = dir_sha256(path)
    out.append({'path': rel, 'resolves': got == want and size == want_size,
                'sha256': got, 'size': size, 'cited_sha256': want,
                'cited_size': want_size})
print(json.dumps(out, indent=1))
