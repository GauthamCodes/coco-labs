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
The frozen v1 site as a built artifact (M3.0; docs/v2/adr/0003-v1-archive.md).

The v1 views are built ONCE from ``9f58b83`` by that commit's own tooling
(``build_v1_archive.sh``), made self-contained, and committed to the orphan
branch ``v1-site``. The Pages deploy copies ``/v1/`` from that branch at a
pinned commit after checking it here; a weekly workflow rebuilds it and
compares.

    python3 lab_web/tools/v1_site.py assemble DIST OUT --pyodide DIR --wheels DIR
    python3 lab_web/tools/v1_site.py verify DIR [--expect-tree SHA256]
    python3 lab_web/tools/v1_site.py compare A B [--out F.json]

``assemble`` copies DIST (the archive as ``build_v1_archive.sh`` writes it)
to OUT and makes it self-hosted: Pyodide's core files (from the pinned npm
package, DIR) and every wheel the v1 worker loads (``micropip`` and its
dependencies, read from DIR's ``pyodide-lock.json``; each file in --wheels
must match the lock's sha256) go to ``OUT/pyodide/``, and the one pinned CDN
URL is rewritten to that directory -- in the page bundle (the worker's
``indexURL``) and in index.html's Content-Security-Policy (removed: the
directory is same-origin, ``'self'`` covers it). Every rewrite is counted and
listed in ``OUT/V1_SITE.json`` with the source commit, the Pyodide version
and the tree hash; ``OUT/SHA256SUMS`` lists every other file. Nothing else
in the build is changed.

``verify`` re-hashes every file against ``SHA256SUMS``, refuses files it
does not list, and (with --expect-tree) checks the tree hash, which is
sha256 over the sorted ``"<sha256>  <path>\\n"`` lines of ``SHA256SUMS``.

``compare`` checks two assembled sites have the same content: every file
equal, except that JSON files may differ only in ``created_utc`` (the
wall-clock stamp the v1 tools write and exclude from every content hash) and
V1_SITE.json / SHA256SUMS, which carry those hashes, are re-derived.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys

SOURCE_COMMIT = '9f58b8338f3364291bc1f85414c798c0c3527c7a'
PYODIDE_VERSION = '314.0.7'
CDN = f'https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/'
BASE = '/coco-labs/v1/'
SELF_HOSTED = f'{BASE}pyodide/'
CORE_FILES = ('pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'pyodide-lock.json', 'python_stdlib.zip')
#: what the v1 worker loads beyond the core (pyodide.worker.ts at 9f58b83:
#: ``loadPackage(['micropip'])``; coco_lab's wheel is served by the site and
#: declares no dependencies)
PACKAGES = ('micropip',)
MANIFEST = 'V1_SITE.json'
SUMS = 'SHA256SUMS'


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def files_under(d):
    out = []
    for root, _, names in os.walk(d):
        for n in names:
            out.append(os.path.relpath(os.path.join(root, n), d).replace(os.sep, '/'))
    return sorted(out)


def tree_hash(sums_text):
    lines = sorted(line for line in sums_text.splitlines() if line.strip())
    return hashlib.sha256(('\n'.join(lines) + '\n').encode()).hexdigest()


def wheels_needed(lock):
    """micropip and everything it depends on, by the lock's own graph."""
    pkgs = lock['packages']
    need, stack = set(), list(PACKAGES)
    while stack:
        n = stack.pop()
        if n in need:
            continue
        need.add(n)
        stack.extend(pkgs[n]['depends'])
    return sorted((pkgs[n]['file_name'], pkgs[n]['sha256']) for n in need)


def assemble(dist, out, pyodide_dir, wheels_dir, source_commit=SOURCE_COMMIT):
    if os.path.exists(out):
        raise SystemExit(f'refusing: {out} exists')
    with open(os.path.join(pyodide_dir, 'package.json')) as f:
        version = json.load(f)['version']
    if version != PYODIDE_VERSION:
        raise SystemExit(f'refusing: npm pyodide is {version}, the v1 build pins {PYODIDE_VERSION}')
    shutil.copytree(dist, out)
    py_out = os.path.join(out, 'pyodide')
    os.makedirs(py_out)
    pyodide_files = {}
    for name in CORE_FILES:
        shutil.copyfile(os.path.join(pyodide_dir, name), os.path.join(py_out, name))
        pyodide_files[name] = {'from': f'npm pyodide@{version}', 'sha256': sha256_file(os.path.join(py_out, name))}
    with open(os.path.join(pyodide_dir, 'pyodide-lock.json')) as f:
        lock = json.load(f)
    for name, want in wheels_needed(lock):
        src = os.path.join(wheels_dir, name)
        got = sha256_file(src)
        if got != want:
            raise SystemExit(f'refusing: {name} sha256 {got} is not the lock\'s {want}')
        shutil.copyfile(src, os.path.join(py_out, name))
        pyodide_files[name] = {'from': f'{CDN}{name} (checked against pyodide-lock.json)', 'sha256': got}

    rewrites = []
    for rel in files_under(out):
        if rel.startswith('pyodide/') or not rel.endswith(('.js', '.html')):
            continue
        p = os.path.join(out, rel)
        with open(p, encoding='utf-8') as f:
            text = f.read()
        if CDN not in text:
            continue
        if rel == 'index.html':
            # the CSP: same-origin, so 'self' already allows it; a bare path is not a CSP source
            new = text.replace(f' {CDN};', ';').replace(f' {CDN} ', ' ')
            what = 'CSP: the CDN source removed (same-origin is \'self\')'
        else:
            new = text.replace(CDN, SELF_HOSTED)
            what = f'Pyodide indexURL -> {SELF_HOSTED}'
        n = text.count(CDN)
        if CDN in new and rel == 'index.html':
            raise SystemExit(f'refusing: the CSP in {rel} still names {CDN}')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(new)
        rewrites.append({'file': rel, 'occurrences': n, 'what': what})
    if not any(r['file'] == 'index.html' for r in rewrites) or len(rewrites) < 2:
        raise SystemExit(f'refusing: expected the CDN URL in index.html and the page bundle, found {rewrites}')
    leftover = [rel for rel in files_under(out) if rel.endswith(('.js', '.html'))
                and CDN in open(os.path.join(out, rel), encoding='utf-8').read()]
    if leftover:
        raise SystemExit(f'refusing: {CDN} still in {leftover}')

    sums = ''.join(f'{sha256_file(os.path.join(out, rel))}  {rel}\n' for rel in files_under(out))
    with open(os.path.join(out, SUMS), 'w') as f:
        f.write(sums)
    manifest = {
        'what': 'The frozen COCO Lab v1 site, served at /v1/ (docs/v2/adr/0003-v1-archive.md)',
        'source_commit': source_commit,
        'built_by': 'lab_web/tools/build_v1_archive.sh (the commit\'s own build_catalog.py, npm ci, '
                    'LAB_BASE=/coco-labs/v1/ vite build, check_dist), then lab_web/tools/v1_site.py assemble',
        'base': BASE,
        'pyodide': {'version': PYODIDE_VERSION, 'self_hosted_at': SELF_HOSTED, 'was': CDN, 'files': pyodide_files},
        'rewrites': rewrites,
        'files': len(sums.splitlines()),
        'bytes': sum(os.path.getsize(os.path.join(out, rel)) for rel in files_under(out) if rel != MANIFEST),
        'tree_sha256': tree_hash(sums),
        'tree_sha256_definition': 'sha256 over the sorted "<sha256>  <path>" lines of SHA256SUMS, each ending in a newline',
    }
    with open(os.path.join(out, MANIFEST), 'w') as f:
        json.dump(manifest, f, indent=1)
        f.write('\n')
    return manifest


def verify(d, expect_tree=None):
    with open(os.path.join(d, SUMS)) as f:
        sums = f.read()
    listed = {}
    for line in sums.splitlines():
        digest, rel = line.split('  ', 1)
        listed[rel] = digest
    problems = []
    present = [rel for rel in files_under(d) if rel not in (SUMS, MANIFEST)]
    for rel in present:
        if rel not in listed:
            problems.append(f'not listed: {rel}')
        elif sha256_file(os.path.join(d, rel)) != listed[rel]:
            problems.append(f'changed: {rel}')
    problems += [f'missing: {rel}' for rel in listed if rel not in present]
    tree = tree_hash(sums)
    if expect_tree and tree != expect_tree:
        problems.append(f'tree {tree} is not the pinned {expect_tree}')
    with open(os.path.join(d, MANIFEST)) as f:
        if json.load(f)['tree_sha256'] != tree:
            problems.append(f'{MANIFEST} tree_sha256 is not SHA256SUMS\'s')
    return {'files': len(listed), 'tree_sha256': tree, 'problems': problems, 'ok': not problems}


def _strip(o):
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k != 'created_utc'}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def compare(a, b):
    fa = {rel for rel in files_under(a) if rel not in (SUMS, MANIFEST)}
    fb = {rel for rel in files_under(b) if rel not in (SUMS, MANIFEST)}
    rows = []
    for rel in sorted(fa & fb):
        pa, pb = os.path.join(a, rel), os.path.join(b, rel)
        if sha256_file(pa) == sha256_file(pb):
            continue
        same = False
        if rel.endswith('.json'):
            try:
                with open(pa) as f1, open(pb) as f2:
                    same = _strip(json.load(f1)) == _strip(json.load(f2))
            except ValueError:
                same = False
        rows.append({'file': rel, 'only_created_utc': same})
    out = {
        'only_in_a': sorted(fa - fb), 'only_in_b': sorted(fb - fa),
        'differ': rows, 'differ_beyond_created_utc': [r['file'] for r in rows if not r['only_created_utc']],
    }
    out['same_content'] = not out['only_in_a'] and not out['only_in_b'] and not out['differ_beyond_created_utc']
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('assemble')
    s.add_argument('dist')
    s.add_argument('out')
    s.add_argument('--pyodide', required=True)
    s.add_argument('--wheels', required=True)
    s = sub.add_parser('verify')
    s.add_argument('dir')
    s.add_argument('--expect-tree')
    s = sub.add_parser('compare')
    s.add_argument('a')
    s.add_argument('b')
    s.add_argument('--out')
    args = ap.parse_args(argv)
    if args.cmd == 'assemble':
        r = assemble(args.dist, args.out, args.pyodide, args.wheels)
        print(json.dumps({k: r[k] for k in ('source_commit', 'files', 'bytes', 'tree_sha256')}))
        return 0
    if args.cmd == 'verify':
        r = verify(args.dir, args.expect_tree)
        print(json.dumps(r))
        return 0 if r['ok'] else 1
    r = compare(args.a, args.b)
    if args.out:
        with open(args.out, 'w') as f:
            json.dump(r, f, indent=1)
    print(json.dumps({'same_content': r['same_content'], 'differ': len(r['differ']),
                      'differ_beyond_created_utc': r['differ_beyond_created_utc']}))
    return 0 if r['same_content'] else 1


if __name__ == '__main__':
    sys.exit(main())
