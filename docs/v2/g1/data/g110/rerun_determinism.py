# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""G1.10: M5's review runner (docs/v2/data/m5/review/rerun_determinism.py) with portable paths.

This cloud container's Playwright cannot drive its installed Firefox and WebKit (protocol
mismatch, and browsers may not be downloaded here), so the v2 corpus runs on Pyodide-in-Node
and Chromium (G1_ENGINES overrides); Firefox and WebKit run in CI on every push.

Replay every recorded session; shard independent fresh models for throughput.

No benchmark claim: processes overlap; conditions are recorded for each shard. Every
per-session hash/chain is retained, plus each unmodified harness output.
"""
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import time

repo = Path(__file__).resolve().parents[5]
web = repo / 'lab_web'
out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).resolve().parent
out.mkdir(parents=True, exist_ok=True)
node = shutil.which('node')  # G1.10: the PATH's node (24.21.0, lab_web/.nvmrc)
site = sys.argv[1]
ENGINES_V2 = os.environ.get('G1_ENGINES', 'node,chromium').split(',')
corpora = {'v1': repo / 'docs/v2/data/m1/determinism/sessions.json',
           'v2': repo / 'docs/v2/data/m5/defects/determinism-v2/sessions.json'}
jobs = []
for corpus, source in corpora.items():
    document = json.loads(source.read_text())
    directory = out / ('determinism-' + corpus)
    directory.mkdir(exist_ok=True)
    for shard in range(10):
        session_file = directory / f'sessions-{shard:02}.json'
        session_file.write_text(json.dumps({**document, 'sessions': document['sessions'][shard * 10:(shard + 1) * 10]}) + '\n')
        for engine in (['node'] if corpus == 'v1' else ENGINES_V2):
            target = directory / 'shards' / f'{engine}-{shard:02}'
            target.mkdir(parents=True, exist_ok=True)
            args = [node, 'tools/perf/determinism.mjs', engine, '--sessions', str(session_file), '--out', str(target), '--hash-version', corpus[-1], '--site', site]
            # G1.13: a WebKit without the host's missing media libraries (no sudo): the wrapper
            if engine == 'webkit' and os.environ.get('G1_WEBKIT_EXE'):
                args += ['--webkit-exe', os.environ['G1_WEBKIT_EXE']]
            jobs.append((corpus, engine, shard, target, args))

start = time.time()
def run(job):
    corpus, engine, shard, target, args = job
    key = 'pyodide-node' if engine == 'node' else engine
    if os.environ.get('G1_RESUME') and (target / f'hashes_{key}.json.gz').exists():
        print(f'{corpus} {engine} {shard:02}: kept (G1_RESUME)', flush=True)   # G1.13: a finished shard
        return 0
    log = target / 'run.log'
    with log.open('w') as stream:
        result = subprocess.run(args, cwd=web, stdout=stream, stderr=subprocess.STDOUT)
    print(f'{corpus} {engine} {shard:02}: exit {result.returncode}, elapsed {time.time() - start:.1f}s', flush=True)
    return result.returncode

with ThreadPoolExecutor(max_workers=int(os.environ.get('G1_WORKERS', '3'))) as pool:
    codes = list(pool.map(run, jobs))
if any(codes):
    sys.exit(1)
for corpus in corpora:
    directory = out / ('determinism-' + corpus)
    for engine in (['node'] if corpus == 'v1' else ENGINES_V2):
        key = 'pyodide-node' if engine == 'node' else engine
        pieces = [json.loads(gzip.decompress((directory / 'shards' / f'{engine}-{i:02}' / f'hashes_{key}.json.gz').read_bytes())) for i in range(10)]
        rows = sorted([session for piece in pieces for session in piece['sessions']], key=lambda r: r['id'])
        assert len(rows) == 100 and len({s['id'] for s in rows}) == 100
        combined = {'engine': key, 'version': pieces[0]['version'], 'seconds': sum(p['seconds'] for p in pieces),
                    'protocol': '10 shards x10 independent recorded sessions; concurrent correctness checks, not benchmark seconds',
                    'conditions': {'start': pieces[0]['conditions']['start'], 'end': pieces[-1]['conditions']['end']},
                    'page_errors': [e for p in pieces for e in p.get('page_errors', [])], 'sessions': rows}
        (directory / f'hashes_{key}.json.gz').write_bytes(gzip.compress(json.dumps(combined).encode()))
    reference = repo / ('docs/v2/data/m1/determinism' if corpus == 'v1' else 'docs/v2/data/m5/defects/determinism-v2')
    with (directory / 'compare.log').open('w') as stream:
        result = subprocess.run([node, 'tools/perf/determinism.mjs', 'compare', '--sessions', str(corpora[corpus]), '--out', str(directory), '--ref', str(reference), '--engines', '1' if corpus == 'v1' else str(len(ENGINES_V2))], cwd=web, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        sys.exit(result.returncode)
print(f'All 100 v1 and {len(ENGINES_V2)}x100 v2 sessions complete in {time.time()-start:.1f}s', flush=True)
