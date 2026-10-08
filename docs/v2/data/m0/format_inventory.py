"""M0.3: count committed files per (schema, version).

Usage: git ls-files -z | python3 -I format_inventory.py REPO_ROOT
Reads every tracked *.json / *.json.gz, looks for a top-level "schema"
(or "format") key and its "version"; prints JSON {schema@version: {count,
dirs}}. Files without a schema key are counted under "(no schema)" by
extension so the remainder is visible, not hidden.
"""
import collections
import gzip
import json
import os
import sys

root = sys.argv[1]
names = sys.stdin.buffer.read().split(b'\0')
hits = collections.defaultdict(lambda: {'count': 0, 'dirs': collections.Counter()})
for raw in names:
    if not raw:
        continue
    rel = raw.decode()
    if not (rel.endswith('.json') or rel.endswith('.json.gz')):
        continue
    p = os.path.join(root, rel)
    try:
        opener = gzip.open if rel.endswith('.gz') else open
        with opener(p, 'rt', encoding='utf-8') as f:
            doc = json.load(f)
    except Exception as e:  # noqa: BLE001 -- report, do not hide
        key = f'(unreadable: {type(e).__name__})'
        doc = None
    if isinstance(doc, dict) and ('schema' in doc or 'format' in doc):
        s = doc.get('schema', doc.get('format'))
        v = doc.get('version', doc.get('format_version', '?'))
        key = f'{s}@{v}' if isinstance(s, str) else '(non-string schema)'
    elif doc is not None:
        key = '(no schema) .json' if rel.endswith('.json') else '(no schema) .json.gz'
    top = '/'.join(rel.split('/')[:3])
    hits[key]['count'] += 1
    hits[key]['dirs'][top] += 1
out = {k: {'count': v['count'], 'dirs': dict(v['dirs'].most_common(8))}
       for k, v in sorted(hits.items())}
print(json.dumps(out, indent=1))
