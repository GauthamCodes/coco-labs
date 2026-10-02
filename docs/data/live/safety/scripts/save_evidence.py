"""save_evidence.py DEST RUN...: copy scripts + gzipped run logs into the repo."""
import gzip
import os
import shutil
import sys

TMP = '/home/gautham/.claude/jobs/eb997671/tmp'
dest = sys.argv[1]
os.makedirs(f'{dest}/scripts', exist_ok=True)
for name in sorted(os.listdir(f'{TMP}/stack')):
    if name.endswith(('.py', '.sh')):
        shutil.copy(f'{TMP}/stack/{name}', f'{dest}/scripts/{name}')
for run in sys.argv[2:]:
    os.makedirs(f'{dest}/{run}', exist_ok=True)
    for f in ('ws.jsonl', 'ros.jsonl', 'stack.log', 'container.log'):
        src = f'{TMP}/runs/{run}/{f}'
        if os.path.exists(src):
            with open(src, 'rb') as i, gzip.open(f'{dest}/{run}/{f}.gz', 'wb') as o:
                shutil.copyfileobj(i, o)
total = sum(os.path.getsize(os.path.join(dp, f))
            for dp, _, fs in os.walk(dest) for f in fs)
print(f'{dest}: {total / 1e6:.2f} MB')
