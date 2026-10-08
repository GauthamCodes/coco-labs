"""M0.3: production bundle sizes, from lab_web/dist on disk.

Usage: python3 -I dist_sizes.py LAB_WEB_DIR > dist_sizes.json
Groups every file under dist/ (raw bytes, and gzip -9 size for text
assets, which is what a compressing CDN would send) and lists the app's
JS/CSS assets one by one.
"""
import gzip
import json
import os
import sys

dist = os.path.join(sys.argv[1], 'dist')
groups, assets = {}, []
for dp, _, fs in os.walk(dist):
    for f in fs:
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, dist)
        size = os.path.getsize(p)
        parts = rel.split(os.sep)
        if parts[0] == 'assets':
            g = 'assets (app JS/CSS/worker)'
        elif parts[0] == 'generated' and len(parts) > 1 and parts[1] == 'py':
            g = 'generated/py (coco_lab wheel for Pyodide)'
        elif parts[0] == 'generated' and len(parts) > 2:
            g = f'generated/{parts[1]}'
        elif parts[0] == 'generated':
            g = f'generated/{parts[1]}'
        else:
            g = rel
        e = groups.setdefault(g, {'files': 0, 'bytes': 0})
        e['files'] += 1
        e['bytes'] += size
        if parts[0] == 'assets' or rel == 'index.html':
            with open(p, 'rb') as fh:
                gz = len(gzip.compress(fh.read(), 9))
            assets.append({'file': rel, 'bytes': size, 'gzip9_bytes': gz})
total = sum(g['bytes'] for g in groups.values())
print(json.dumps({'dist_total_bytes': total,
                  'dist_files': sum(g['files'] for g in groups.values()),
                  'groups': dict(sorted(groups.items(), key=lambda kv: -kv[1]['bytes'])),
                  'app_assets': sorted(assets, key=lambda a: -a['bytes'])}, indent=1))
