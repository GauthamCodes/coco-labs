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
Convert the recordings behind every Case File (M3.3; ADR 0005).

    py.sh lab_web/tools/build_casefiles.py OUT_DIR [--runs ~/coco_lab_runs] [--only ID ...]

Needs ROS (rosbag2_py) and the raw bags in ``~/coco_lab_runs`` (never
modified): so it runs on the development machine, not in CI. For each
recording named by ``lab_web/casefiles/cases.yaml`` it

1. checks the source against the checksum a committed manifest already
   cites, by THAT lab's own definition (ADR 0005) -- a mismatch stops the
   build, it is never patched;
2. converts it with ``coco_lab_ros.adapter`` at ``summary`` detail (Lab 4:
   cut at the run's own first terminal state + 2 s of log time, the rule of
   ``docs/data/p05_bagtimes.py``; Lab 5: the run's recorded window);
3. writes ``OUT_DIR/<id>.mcap`` (uncompressed) and ``OUT_DIR/build.json``.

``lab_web/tools/pack_casefiles.mjs OUT_DIR`` then repacks them (zstd, the
same messages) into ``lab_web/casefiles/`` with ``index.json``.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
CASES = os.path.join(REPO, 'lab_web', 'casefiles', 'cases.yaml')
#: seconds of recording kept before and after a Lab 5 run's recorded window (its FollowPath
#: request to its end): the approach and the stop, as context
LAB5_CONTEXT_S = 5.0
#: seconds kept before a mislocalised run's recorded /initialpose (the wrong belief told to AMCL)
INJECT_CONTEXT_S = 3.0
sys.path.insert(0, os.path.join(REPO, 'coco_lab_ros'))
sys.path.insert(0, os.path.join(REPO, 'coco_schemas'))


class Mismatch(SystemExit):
    """A recording whose checksum is not the one a committed manifest cites (B.5: stop)."""


# -- the labs' own checksum definitions (ADR 0005) ---------------------------------

def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def p05_sha_dir(path):
    """docs/data/p05_evidence.py ``_sha_dir``, verbatim (Lab 4)."""
    h = hashlib.sha256()
    for root, _, files in sorted(os.walk(path)):
        for f in sorted(files):
            with open(os.path.join(root, f), 'rb') as fh:
                h.update(f.encode() + b'\0' + fh.read())
    return h.hexdigest()


def export_dir_sha256(root):
    """coco_lab_ros.export.dir_sha256 (Lab 1C): sorted "relpath sha256" lines, hashed."""
    lines = []
    for dirpath, _, files in os.walk(root):
        for f in files:
            p = os.path.join(dirpath, f)
            lines.append(f'{os.path.relpath(p, root)} {sha_file(p)}\n')
    return hashlib.sha256(''.join(sorted(lines)).encode()).hexdigest()


def check(case, runs):
    """Compare a case's source with its committed citation; return what was checked."""
    want = case.get('cite')
    if not want:
        return {'checked': False, 'why': 'no committed manifest cites this bag by checksum'}
    bag = os.path.join(runs, case['bags'][0])
    got = {'p05_sha_dir': p05_sha_dir, 'export_dir_sha256': export_dir_sha256,
           'lab5_bag_0': lambda b: sha_file(os.path.join(b, 'bag_0.mcap'))}[want['definition']](bag)
    if got != want['sha256']:
        raise Mismatch(f"{case['id']}: {want['definition']}({case['bags'][0]}) = {got}, but "
                       f"{want['file']} cites {want['sha256']} -- stop (M3 prompt B.5)")
    return {'checked': True, 'definition': want['definition'], 'sha256': got, 'cited_in': want['file']}


# -- which recordings each group is ------------------------------------------------

def load_cases():
    import yaml
    with open(CASES, encoding='utf-8') as f:
        return yaml.safe_load(f)


def enumerate_cases(doc, runs):
    out = []
    for g in doc['groups']:
        src = g['source']
        kind = src['kind']
        if kind == 'lab1c':
            with open(os.path.join(REPO, 'docs', 'data', 'lab1c', 'runs.json')) as f:
                by_dir = {os.path.basename(r['dir']): r for r in json.load(f)['runs']}
            for run in src['runs']:
                rec = by_dir[run]
                out.append({'id': f'lab1_{run}', 'group': g['id'], 'title': f'Lab 1 · {run[4:]}',
                            'bags': [f'lab1c/{run}/bag'], 'case': {'lab': 1, 'run': run},
                            'cite': {'file': 'docs/data/lab1c/runs.json',
                                     'definition': 'export_dir_sha256',
                                     'sha256': rec['metrics']['bag']['sha256']}})
        elif kind == 'lab2_kidnap':
            dirs = sorted(d for d in os.listdir(os.path.join(runs, src['root']))
                          if d.startswith(src['prefix'])
                          and os.path.isdir(os.path.join(runs, src['root'], d, 'bag')))
            for d in dirs:
                cid = 'lab2_' + re.sub(r'[^a-z0-9]+', '_', d.lower()).strip('_')
                out.append({'id': cid, 'group': g['id'], 'title': f'Lab 2 · {d}',
                            'bags': [f"{src['root']}/{d}/bag"],
                            'case': {'lab': 2, 'session': d, 'void': '.void' in d}})
        elif kind == 'lab4':
            with open(os.path.join(REPO, src['manifest'])) as f:
                m = json.load(f)
            for r in m['runs']:
                out.append({'id': 'lab4_' + r['id'].lower(), 'group': g['id'],
                            'title': f"Lab 4 · {r['id']}", 'bags': [f"{src['root']}/{r['id']}/bag"],
                            'case': {'lab': 4, 'run': r['id'], 'world_to_map': [2, 0]},
                            'cut': 'first_terminal',
                            'cite': {'file': src['manifest'], 'definition': 'p05_sha_dir',
                                     'sha256': r['record']['bag_sha256']}})
            for v in src.get('void', []):
                out.append({'id': 'lab4_' + re.sub(r'[^a-z0-9]+', '_', v.lower()).strip('_'),
                            'group': g['id'], 'title': f'Lab 4 · {v} (void)',
                            'bags': [f"{src['root']}/{v}/bag"],
                            'case': {'lab': 4, 'run': v, 'void': True, 'world_to_map': [2, 0]},
                            'cut': 'first_terminal'})
        elif kind == 'lab5':
            for mf in sorted(glob.glob(os.path.join(REPO, src['manifests'], '*', 'manifest.json'))):
                scenario = os.path.basename(os.path.dirname(mf))
                with open(mf) as f:
                    m = json.load(f)
                for r in m['runs']:
                    run = r['record']['run']
                    out.append({'id': 'lab5_' + run.lower(), 'group': g['id'],
                                'title': f"Lab 5 · {scenario} · {r['controller']} {r['id']}",
                                'bags': [f"{src['root']}/{run}/bag"],
                                'case': {'lab': 5, 'scenario': scenario, 'controller': r['controller'],
                                         'run': run, 'actor_radius': 0.25 if r.get('actors') else None},
                                # the run's recorded window, widened by LAB5_CONTEXT_S each side: a
                                # mislocalised run aborts within 8 ms, so its window alone is empty
                                'window': [r['window'][0] - LAB5_CONTEXT_S, r['window'][1] + LAB5_CONTEXT_S],
                                'cite': {'file': os.path.relpath(mf, REPO), 'definition': 'lab5_bag_0',
                                         'sha256': r['record']['bag_sha256']}})
        elif kind == 'multi':
            for c in src['cases']:
                entry = {'id': c['id'], 'group': g['id'], 'title': c['title'], 'bags': c['bags'],
                         'case': {'lab': g['lab'], 'world_to_map': [2, 0]}}
                wf = c.get('window_from')
                if wf:   # a drive's own recorded window, from the committed evidence that scores it
                    with open(os.path.join(REPO, wf['file'])) as f:
                        d = [x for x in json.load(f)['drives']
                             if x['session'] == wf['session'] and x['drive'] == wf['drive']]
                    if len(d) != 1:
                        raise SystemExit(f"{c['id']}: {wf} names {len(d)} drives")
                    entry['window'] = [d[0]['t0'], d[0]['t1']]
                out.append(entry)
        elif kind == 'group':
            continue
        else:
            raise SystemExit(f'unknown source kind {kind!r} in group {g["id"]}')
    for c in out:
        if c['case'].get('actor_radius') is None:
            c['case'].pop('actor_radius', None)
        c['case'].update({'id': c['id'], 'group': c['group'], 'title': c['title']})
    ids = [c['id'] for c in out]
    if len(ids) != len(set(ids)):
        raise SystemExit('two Case Files share an id')
    return out


def first_terminal_window(bag):
    """Log window of a Lab 4 run: the bag's start to its first terminal state + 2 s (p05_bagtimes)."""
    from coco_lab_ros import adapter as A
    first, end = None, None
    for _, m, log in A.read_bag(bag, ['/mission/state']):
        first = log if first is None else min(first, log)
        if end is None and A.parse_kv(m.data).get('state') in ('COMPLETE', 'ABORT'):
            end = log
    return (0, end + 2_000_000_000) if end is not None else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--runs', default=os.path.expanduser('~/coco_lab_runs'))
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--group', nargs='*', help='only these groups (build.json is merged, not replaced)')
    a = ap.parse_args(argv)
    from coco_lab_ros import adapter as A
    git_sha = subprocess.run(['git', '-C', REPO, 'rev-parse', 'HEAD'], capture_output=True,
                             text=True).stdout.strip()
    os.makedirs(a.out, exist_ok=True)
    cases = enumerate_cases(load_cases(), a.runs)
    if a.only:
        cases = [c for c in cases if c['id'] in a.only]
    if a.group:
        cases = [c for c in cases if c['group'] in a.group]
    built = []
    for c in cases:
        bags = [os.path.join(a.runs, b) for b in c['bags']]
        missing = [b for b in bags if not os.path.isdir(b)]
        if missing:
            raise SystemExit(f"{c['id']}: recording missing: {missing} -- stop (M3 prompt B.5)")
        checked = check(c, a.runs)
        log_window = first_terminal_window(bags[0]) if c.get('cut') == 'first_terminal' else None
        window = tuple(c['window']) if c.get('window') else None
        if c['case'].get('scenario') == 'mislocalised' and window:
            # the wrong belief was told to AMCL (/initialpose) about 10 s before the run: the
            # Case File starts INJECT_CONTEXT_S before that recorded message, so it holds the
            # moment localisation was made wrong as well as the abort
            told = [log for _, _, log in A.read_bag(bags[0], ['/initialpose'])]
            told = [t * 1e-9 for t in told if t * 1e-9 <= window[0]]
            if not told:
                raise SystemExit(f"{c['id']}: no /initialpose before its run -- the recording is not what Lab 5 says")
            window = (min(window[0], told[-1] - INJECT_CONTEXT_S), window[1])
        data, s = A.convert(bags if len(bags) > 1 else bags[0], c['case'], 'summary',
                            window=window, log_window=log_window, source_root=a.runs,
                            git_sha=git_sha)
        with open(os.path.join(a.out, c['id'] + '.mcap'), 'wb') as f:
            f.write(data)
        built.append({'id': c['id'], 'group': c['group'], 'title': c['title'], 'bags': c['bags'],
                      'case': c['case'], 'run_id': s['run_id'], 'bytes_uncompressed': len(data),
                      'messages': s['messages'], 'rows': s['rows'], 'checksum': checked,
                      'window': window and list(window), 'log_window_ns': log_window and list(log_window)})
        print(f"{c['id']}: {len(data):,} B, {s['messages']} messages, "
              f"checksum {'ok (' + checked['definition'] + ')' if checked['checked'] else 'not cited'}",
              flush=True)
    path = os.path.join(a.out, 'build.json')
    if (a.only or a.group) and os.path.isfile(path):   # a partial rebuild: merge into the last build
        with open(path) as f:
            old = json.load(f)
        mine = {c['id'] for c in built}
        order = [c['id'] for c in enumerate_cases(load_cases(), a.runs)]
        merged = {c['id']: c for c in old['cases'] if c['id'] not in mine}
        merged.update({c['id']: c for c in built})
        built = [merged[i] for i in order if i in merged]
    with open(path, 'w') as f:
        json.dump({'adapter': A.ADAPTER_VERSION, 'detail': 'summary', 'git_sha': git_sha,
                   'cases': built}, f, indent=1)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
