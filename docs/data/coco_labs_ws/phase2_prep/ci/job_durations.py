"""Duration of every job in every SUCCESSFUL run of CI and Lab, from the GitHub API."""
import json
import subprocess
from datetime import datetime


def gh(path):
    out = subprocess.run(['gh', 'api', '--paginate', path], capture_output=True, text=True, check=True).stdout
    # --paginate concatenates JSON objects; split them
    dec, i, objs = json.JSONDecoder(), 0, []
    out = out.strip()
    while i < len(out):
        obj, j = dec.raw_decode(out, i)
        objs.append(obj)
        i = j
        while i < len(out) and out[i].isspace():
            i += 1
    return objs


def ts(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


for repo in ('GauthamCodes/coco-labs', 'GauthamCodes/coco-robot-jazzy-2.0'):
    for wf in ('ci.yml', 'lab.yml'):
        try:
            pages = gh(f'repos/{repo}/actions/workflows/{wf}/runs?status=success&per_page=100')
        except subprocess.CalledProcessError:
            continue
        runs = [r for p in pages for r in p['workflow_runs']]
        per_job = {}
        for r in runs:
            for p in gh(f"repos/{repo}/actions/runs/{r['id']}/attempts/{r['run_attempt']}/jobs?per_page=100"):
                for job in p['jobs']:
                    if job['conclusion'] != 'success' or not job['completed_at']:
                        continue
                    mins = (ts(job['completed_at']) - ts(job['started_at'])).total_seconds() / 60
                    per_job.setdefault(job['name'], []).append((round(mins, 1), r['id'], r['head_sha'][:7]))
        for name, rows in sorted(per_job.items()):
            rows.sort()
            print(f"{repo.split('/')[1]:22} {wf:8} job={name:18} green runs={len(rows):3} "
                  f"median={rows[len(rows)//2][0]:5} min  slowest={rows[-1][0]} min (run {rows[-1][1]}, {rows[-1][2]})")
