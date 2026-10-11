"""Review A.2.3: recompute every cited source-bag checksum from ~/coco_lab_runs,
with independent implementations of each lab's definition, and compare with
(a) the committed data file that cites it and (b) the Case File index."""
import hashlib, json, os, sys, glob
R = '/home/gautham/review/coco-labs-m3'
RUNS = os.path.expanduser('~/coco_lab_runs')
idx = json.load(open(f'{R}/lab_web/casefiles/index.json'))

def fsha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def export_dir_sha(root):  # lab1: sorted "relpath sha\n" lines
    lines = []
    for dp, _, fs in os.walk(root):
        for n in fs:
            p = os.path.join(dp, n); lines.append(f'{os.path.relpath(p, root)} {fsha(p)}\n')
    return hashlib.sha256(''.join(sorted(lines)).encode()).hexdigest()

def p05_sha_dir(path):  # lab4: name\0bytes over sorted walk
    h = hashlib.sha256()
    for root, _, files in sorted(os.walk(path)):
        for f in sorted(files):
            h.update(f.encode() + b'\0' + open(os.path.join(root, f), 'rb').read())
    return h.hexdigest()

def cited(entry):
    c = entry['checksum']; f = f"{R}/{c['cited_in']}" if not c['cited_in'].startswith('/') else c['cited_in']
    run = entry['case'].get('run')
    for path in glob.glob(f) if '*' in f else [f]:
        d = json.load(open(path))
        for r in d.get('runs', []):
            names = {str(r.get(k)) for k in ('run', 'name', 'id', 'label')}
            if 'dir' in r: names.add(os.path.basename(r['dir']))
            names.add(str(r.get('record', {}).get('run')))
            if run in names:
                return (r.get('metrics', {}).get('bag', {}).get('sha256')
                        or r.get('record', {}).get('bag_sha256')), path
    return None, f

rows, ok = [], 0
for e in idx['casefiles']:
    c = e.get('checksum') or {}
    if not c.get('checked'): continue
    bag = os.path.join(RUNS, e['bags'][0])
    d = c['definition']
    if d == 'export_dir_sha256': got = export_dir_sha(bag)
    elif 'sha_dir' in d: got = p05_sha_dir(bag)
    else: got = fsha(os.path.join(bag, 'bag_0.mcap'))
    cv, where = cited(e)
    good = got == c['sha256'] == cv
    ok += good
    rows.append({'id': e['id'], 'definition': d, 'recomputed': got, 'index': c['sha256'],
                 'cited': cv, 'cited_in': os.path.relpath(where, R), 'match': good})
    print(('OK ' if good else 'BAD'), e['id'], d, got[:12], (cv or 'NONE')[:12])
out = {'checked': len(rows), 'matching': ok, 'rows': rows}
json.dump(out, open(sys.argv[1], 'w'), indent=1)
print(f'{ok}/{len(rows)} match')
