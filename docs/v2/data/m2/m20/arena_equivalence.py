"""M2.0 evidence: old (M1) Arena vs new Arena, and sliced/amended steps, natively."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WT = Path(sys.argv[1])
SESS = json.load(open(sys.argv[2]))['sessions']
N = int(sys.argv[3]) if len(sys.argv) > 3 else len(SESS)
tmp = Path(tempfile.mkdtemp())
shutil.copytree(WT / 'coco_lab' / 'coco_lab', tmp / 'coco_lab_old')
old = subprocess.run(['git', '-C', str(WT), 'show', '0a2516a:coco_lab/coco_lab/arena.py'],
                     capture_output=True, text=True, check=True).stdout
(tmp / 'coco_lab_old' / 'arena.py').write_text(old)
sys.path[:0] = [str(tmp), str(WT / 'coco_lab')]
import coco_lab_old.arena as A0  # noqa: E402
import coco_lab.arena as A1  # noqa: E402
import yaml  # noqa: E402

spec = yaml.safe_load(open(WT / "worlds" / "coco_arena_v1.yaml"))


def events(mod, s, k):
    return [mod.InputEvent(**{**x, 'tick': k}) for x in s['inputs'] if x['tick'] == k]


def clean(x):
    return {k: v for k, v in x.items() if k != 'tick'}


diff_old = diff_slice = ticks = amended = 0
for s in SESS[:N]:
    for x in s['inputs']:
        x.update(clean(x))
    a0 = A0.Arena(spec, s['seed'], planner=s['planner'], on_plan_batch=lambda c, m: None)
    a1 = A1.Arena(spec, s['seed'], planner=s['planner'], on_plan_batch=lambda c, m: None)
    a2 = A1.Arena(spec, s['seed'], planner=s['planner'], on_plan_batch=lambda c, m: None)
    for k in range(s['ticks']):
        h0 = a0.step(events(A0, s, k)).state_hash
        h1 = a1.step(events(A1, s, k)).state_hash
        ev = events(A1, s, k)
        # sliced: begin with the first input, advance 7 events, amend with the rest, slices of 13
        a2.begin_step([])
        a2.advance(7)
        if ev:
            a2.amend(ev)
            amended += 1
        while not a2.advance(13):
            pass
        h2 = a2.finish_step().state_hash
        ticks += 1
        diff_old += h0 != h1
        diff_slice += h1 != h2
    assert a1.chain == a2.chain or diff_slice
print(json.dumps({'sessions': N, 'ticks': ticks, 'ticks_with_amend': amended,
                  'old_vs_new_differing': diff_old, 'whole_vs_sliced_amended_differing': diff_slice,
                  'python': sys.version.split()[0]}))
shutil.rmtree(tmp)
