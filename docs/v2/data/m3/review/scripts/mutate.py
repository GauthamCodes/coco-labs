"""A.2.3 / A.2.4 mutation tests in a scratch copy (never committed):
1. an explanation sentence in a Case File with no evidence -> the CI catalog build must fail
2. the same sentence with an evidence reference that does not resolve -> must fail
3. mission 7 tick 128 -> 129 (no longer its derived moment) -> must fail
Each mutation is applied to a fresh copy of the original file and restored after."""
import os, subprocess, json, sys
M = '/home/gautham/review/m3_tmp/mut'
CASES = f'{M}/lab_web/casefiles/cases.yaml'
MIS7 = [f for f in os.listdir(f'{M}/lab_web/missions') if f.startswith('07')][0]
MIS7 = f'{M}/lab_web/missions/{MIS7}'
env = dict(os.environ, PYTHONPATH=f'{M}/coco_lab', PYTHONDONTWRITEBYTECODE='1')
for k in ('AMENT_PREFIX_PATH', 'COLCON_PREFIX_PATH', 'ROS_DISTRO'): env.pop(k, None)

def build():
    p = subprocess.run(['/usr/bin/python3', 'lab_web/tools/build_catalog.py'], cwd=M, env=env,
                       capture_output=True, text=True)
    tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
    return p.returncode, tail

def mutate(path, old, new):
    orig = open(path).read(); assert orig.count(old) == 1, old
    open(path, 'w').write(orig.replace(old, new)); return orig

results = {}
code, tail = build(); results['unmodified'] = {'exit': code, 'tail': tail}
SENT = ("      - label: SIMULATION RESULT\n        text: >-\n          A throwaway review claim: the greedy run was"
        " the fastest of the three.\n")
ANCHOR = "    explain:\n      - label: SIMULATION RESULT\n        text: >-\n          Each run planned once"
for name, ev in (('claim_without_evidence', ''),
                 ('claim_with_unresolvable_evidence', "        evidence: ['docs/RESULTS.md \"No Such Section\"']\n")):
    orig = mutate(CASES, ANCHOR, "    explain:\n" + SENT + ev + ANCHOR[len("    explain:\n"):])
    code, tail = build(); results[name] = {'exit': code, 'tail': tail}
    open(CASES, 'w').write(orig)
orig = mutate(MIS7, 'moment: refusal, tick: 128,', 'moment: refusal, tick: 129,')
code, tail = build(); results['mission7_tick_not_derived'] = {'exit': code, 'tail': tail}
open(MIS7, 'w').write(orig)
code, tail = build(); results['restored'] = {'exit': code, 'tail': tail}
json.dump(results, open(sys.argv[1], 'w'), indent=1)
for k, v in results.items(): print(k, v['exit'], v['tail'][-1] if v['tail'] else '')
