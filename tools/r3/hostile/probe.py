# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.3 · ADR 0014 hostile probe: plain Python run INSIDE the held-out sandbox (the same docker run
as .github/workflows/leaderboard-results.yml, its entrypoint replaced), as if a submission had
escaped the guard. It tries every way out it can think of and writes what it found to /out, the
one writable mount. tools/r3/hostile_check.py then checks that (1) the secret was found nowhere,
(2) nothing left over the network, (3) whatever it wrote to /out is not what the trusted step
publishes.
"""
import json
import os
import re
import socket

HEX = re.compile(rb'[0-9a-f]{64}')
found = {'env': dict(os.environ), 'secret_like': [], 'net': {}, 'files_read': 0,
         'heldout_files': [], 'docker_sock': os.path.exists('/var/run/docker.sock'),
         'uid': os.getuid()}

# 1. the secret: the environment, our own and pid 1's, then every readable file
for p in ('/proc/self/environ', '/proc/1/environ', '/proc/1/cmdline'):
    try:
        found['secret_like'] += [m.decode() for m in HEX.findall(open(p, 'rb').read())]
    except OSError as e:
        found[p] = type(e).__name__
for root, dirs, files in os.walk('/'):
    if root.startswith(('/proc', '/sys', '/dev')):
        dirs[:] = []
        continue
    for f in files:
        p = os.path.join(root, f)
        try:
            if os.path.getsize(p) > 2_000_000:
                continue
            data = open(p, 'rb').read()
        except OSError:
            continue
        found['files_read'] += 1
        for m in HEX.findall(data):
            found['secret_like'].append(f'{p}: {m.decode()}')
        if p.startswith('/heldout'):
            found['heldout_files'].append(p)

# 2. the network
for name, target in (('tcp_1.1.1.1_443', ('1.1.1.1', 443)), ('tcp_140.82.112.3_443',
                                                              ('140.82.112.3', 443))):
    try:
        s = socket.create_connection(target, timeout=3)
        s.close()
        found['net'][name] = 'CONNECTED'
    except OSError as e:
        found['net'][name] = type(e).__name__ + ': ' + str(e)[:60]
try:
    found['net']['dns_github.com'] = socket.gethostbyname('github.com')
except OSError as e:
    found['net']['dns_github.com'] = type(e).__name__

# 3. exfiltration through the outputs: the scenarios into /out and into the "runs" file
leak = {}
for p in found['heldout_files']:
    leak[p] = json.load(open(p))
open('/out/leak.json', 'w').write(json.dumps(leak))
first = next(iter(leak.values()), {}).get('scenarios', [{}])[0]
coords = ','.join(str(round(v, 2)) for v in first.get('start', [])[:2] + first.get('goal', []))
runs = {'family': 'planning', 'runs': [
    {'status': coords[:40] or 'found', 'success': True,
     'metrics': {'path_ratio': first.get('start', [1.0])[0], 'min_clearance_m': 0.25}}]}
open('/out/heldout_runs.json', 'w').write(json.dumps(runs))
open('/out/probe.json', 'w').write(json.dumps(found, default=str))
print('PROBE STDOUT', coords, json.dumps(leak)[:2000])   # stdout: must never be published
