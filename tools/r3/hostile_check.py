#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.3 · ADR 0014: attack the secret held-out scheme in the REAL sandbox, locally (needs docker).

    tools/r3/hostile_check.py --out docs/v2/r3/data/heldout [--docker "sg docker -c"]

1. A fresh random secret (never written to disk, never printed; only its sha256 is recorded)
   generates a depot-narrow-30 held-out file exactly as the workflow does.
2. ``probe.py`` runs inside the workflow's exact ``docker run`` (entrypoint replaced by python),
   as a guard-escaped submission would: it hunts for the secret (environment, /proc, every
   readable file), tries the network, and writes the scenarios into /out and its stdout.
3. Three hostile ``algorithm.py`` submissions run through the real ``heldout`` command: one reads
   the scenario file, one reads the environment (both must be refused), one "memorises".
4. The trusted aggregator runs on whatever the sandbox wrote.

Verdicts (each must hold, else the ADR is NOT accepted): the secret appears in nothing the
sandbox could see or write; no connection or DNS succeeded; the published aggregate holds only
its allowed keys; the probe's leak files and stdout are not part of what is published; the guard
refuses the two hostile files. Written to OUT/hostile.json (and the README there).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
PY = sys.executable
SUITE = 'depot-narrow-30'
FLAGS = ('--rm --network none --read-only --tmpfs /tmp:size=256m --cpus 2 --memory 4g '
         '--memory-swap 4g --pids-limit 256 --cap-drop ALL --security-opt no-new-privileges '
         '--user 65534:65534')


def docker(prefix, args, log=None):
    cmd = 'docker ' + args
    full = f'{prefix} {shlex.quote(cmd)}' if prefix else cmd
    with open(log, 'w') if log else open(os.devnull, 'w') as f:
        return subprocess.run(full, shell=True, stdout=f, stderr=subprocess.STDOUT).returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', required=True)
    ap.add_argument('--docker', default='sg docker -c')
    o = ap.parse_args()
    out = Path(o.out)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='coco_hostile_'))
    secret = secrets.token_hex(32)
    report = {'suite': SUITE, 'secret_sha256': hashlib.sha256(secret.encode()).hexdigest(),
              'checks': {}}
    try:
        ho = work / 'heldout'
        ho.mkdir()
        env = dict(os.environ, COCO_HELDOUT_SECRET=secret, PYTHONDONTWRITEBYTECODE='1')
        subprocess.run([PY, '-P', str(REPO / 'tools/r3/heldout.py'), 'generate', SUITE, '--head',
                        'f' * 40, '--out', str(ho / f'{SUITE}.json')], env=env, check=True,
                       stdout=subprocess.DEVNULL)
        scen = json.loads((ho / f'{SUITE}.json').read_text())['scenarios']
        rc = docker(o.docker, f'build -q -t coco-verifier -f {REPO}/tools/r2/verifier.Dockerfile '
                    f'{REPO}', work / 'build.log')
        report['image_build_rc'] = rc
        if rc:
            raise SystemExit('docker build failed: ' + (work / 'build.log').read_text()[-2000:])
        mounts = (f'-v {work}/probe:/probe:ro -v {ho}/{SUITE}.json:/heldout/{SUITE}.json:ro '
                  f'-v {work}/pout:/out')
        (work / 'probe').mkdir()
        shutil.copy(REPO / 'tools/r3/hostile/probe.py', work / 'probe' / 'probe.py')
        (work / 'pout').mkdir()
        os.chmod(work / 'pout', 0o777)
        report['probe_rc'] = docker(o.docker, f'run {FLAGS} {mounts} --entrypoint python '
                                    'coco-verifier /probe/probe.py', work / 'probe_stdout.log')
        probe = json.loads((work / 'pout' / 'probe.json').read_text())
        everything = b''.join(p.read_bytes() for p in (work / 'pout').iterdir()) + \
            (work / 'probe_stdout.log').read_bytes()
        c = report['checks']
        c['probe_ran_as_uid_65534'] = probe['uid'] == 65534
        c['probe_read_files'] = probe['files_read']
        c['secret_not_in_environment'] = secret not in json.dumps(probe['env'])
        c['secret_not_found_anywhere'] = not any(secret in s for s in probe['secret_like'])
        c['secret_not_in_any_sandbox_output'] = secret.encode() not in everything
        c['no_docker_socket'] = not probe['docker_sock']
        c['network'] = probe['net']
        c['no_connection'] = not any(v == 'CONNECTED' for v in probe['net'].values())
        c['no_dns'] = probe['net']['dns_github.com'] in ('gaierror', 'OSError')
        c['probe_saw_heldout_file'] = probe['heldout_files']   # expected: the scenarios are its input
        # the trusted step: aggregate what the sandbox left; publish only that
        agg = work / 'agg.json'
        r = subprocess.run([PY, '-P', str(REPO / 'tools/r3/heldout.py'), 'aggregate',
                            str(work / 'pout' / 'heldout_runs.json'), '--out', str(agg)],
                           capture_output=True, text=True)
        published = agg.read_text() if r.returncode == 0 else ''
        c['aggregate_rc'] = r.returncode
        c['published'] = json.loads(published) if published else None
        allowed = {'family', 'n', 'successes', 'wilson95', 'path_ratio_median',
                   'min_clearance_m_median'}
        c['published_keys_allowed'] = bool(published) and set(json.loads(published)) <= allowed
        coords = [f'{v:.2f}' for s in scen for v in s['start'][:2] + s['goal']]
        c['coordinates_in_published_text'] = [x for x in coords if x in published]
        # R4 Part A: the probe falsifies path_ratio on purpose (T5, accepted in ADR 0014), so that
        # one median CAN equal a coordinate at 3 significant digits (it did when the coordinate
        # was < 10: '7.35'; R3's 13.6 vs '13.65' passed only by formatting). The verdict is
        # therefore over every OTHER published field; the residual's match is reported, not hidden.
        rest = json.dumps({k: v for k, v in json.loads(published).items()
                           if k != 'path_ratio_median'}) if published else ''
        c['coordinates_outside_the_residual'] = [x for x in coords if x in rest]
        c['residual_equals_a_coordinate'] = sorted(set(c['coordinates_in_published_text'])
                                                   - set(c['coordinates_outside_the_residual']))
        c['leak_files_not_published'] = sorted(p.name for p in (work / 'pout').iterdir()
                                               if p.name != 'heldout_runs.json')
        # residual (ADR 0014, T5): a falsified median can carry one rounded number per metric
        c['residual_one_number_per_metric'] = (c['published'] or {}).get('path_ratio_median')
        # 3. hostile algorithm files through the real heldout command
        subs = {}
        for name in ('read_heldout', 'env_secret', 'memorise'):
            d = work / 'subs' / SUITE / name
            shutil.copytree(REPO / 'tools/r3/hostile' / name, d)
            so = work / f'out_{name}'
            so.mkdir()
            os.chmod(so, 0o777)
            rc = docker(o.docker, f'run {FLAGS} -v {d}:/submissions/{SUITE}/{name}:ro '
                        f'-v {ho}/{SUITE}.json:/heldout/{SUITE}.json:ro -v {so}:/out coco-verifier '
                        f'heldout /submissions/{SUITE}/{name} --scenarios /heldout/{SUITE}.json '
                        '--out /out --workers 2', work / f'{name}.log')
            log = (work / f'{name}.log').read_text()
            entry = {'container_rc': rc, 'refused_by_guard': 'GuardError' in log or
                     'not an allowed' in log or 'not allowed' in log}
            runs = so / 'heldout_runs.json'
            if runs.exists():
                a = subprocess.run([PY, '-P', str(REPO / 'tools/r3/heldout.py'), 'aggregate',
                                    str(runs), '--out', str(so / 'agg.json')], capture_output=True)
                entry['aggregate'] = json.loads((so / 'agg.json').read_text()) \
                    if a.returncode == 0 else 'invalid'
            entry['secret_in_log'] = secret in log
            entry['log_tail'] = log.strip().splitlines()[-1][:200] if log.strip() else ''
            subs[name] = entry
        report['submissions'] = subs
        c['hostile_files_refused'] = all(
            subs[n]['container_rc'] != 0 or subs[n].get('aggregate', {}) == 'invalid'
            or (isinstance(subs[n].get('aggregate'), dict) and subs[n]['aggregate']['successes'] == 0)
            for n in ('read_heldout', 'env_secret'))
        must = ('secret_not_in_environment', 'secret_not_found_anywhere',
                'secret_not_in_any_sandbox_output', 'no_docker_socket', 'no_connection', 'no_dns',
                'published_keys_allowed', 'probe_ran_as_uid_65534', 'hostile_files_refused')
        report['pass'] = all(c[k] is True for k in must) and not c['coordinates_outside_the_residual']
        report['failed'] = [k for k in must if c[k] is not True] + \
            (['coordinates_outside_the_residual'] if c['coordinates_outside_the_residual'] else [])
    finally:
        shutil.rmtree(work, ignore_errors=True)
        secret = None
    (out / 'hostile.json').write_text(json.dumps(report, indent=1, sort_keys=True) + '\n')
    print('HOSTILE CHECK', 'PASS' if report.get('pass') else 'FAIL', report.get('failed'))
    return 0 if report.get('pass') else 1


if __name__ == '__main__':
    sys.exit(main())
