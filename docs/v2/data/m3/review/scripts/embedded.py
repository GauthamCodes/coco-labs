"""A.2.3: each Case File's embedded manifest (inside zstd chunks) must cite every file of
its source bag(s) by the sha256 that file has on disk in ~/coco_lab_runs today."""
import hashlib, json, os, struct, subprocess, sys
R = '/home/gautham/review/coco-labs-m3'
RUNS = os.path.expanduser('~/coco_lab_runs')
idx = json.load(open(f'{R}/lab_web/casefiles/index.json'))

def fsha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def records(b, o, end):
    while o < end:
        op = b[o]; (n,) = struct.unpack_from('<Q', b, o + 1)
        yield op, b[o + 9:o + 9 + n]; o += 9 + n

def plain(data):
    """All record bytes, with every chunk decompressed."""
    out = [data]
    for op, body in records(data, 8, len(data) - 8):
        if op == 0x06:
            o = 28; (cn,) = struct.unpack_from('<I', body, o); comp = body[o + 4:o + 4 + cn].decode(); o += 4 + cn
            (n,) = struct.unpack_from('<Q', body, o); o += 8
            raw = body[o:o + n]
            out.append(subprocess.run(['zstd', '-dc'], input=raw, capture_output=True, check=True).stdout if comp == 'zstd' else raw)
    return b''.join(out)

ok, rows = 0, []
for e in idx['casefiles']:
    b = plain(open(f"{R}/lab_web/casefiles/{e['id']}.mcap", 'rb').read())
    files = []
    for bag in e['bags']:
        d = os.path.join(RUNS, bag)
        files += [(bag, n, fsha(os.path.join(d, n))) for n in sorted(os.listdir(d)) if os.path.isfile(os.path.join(d, n))]
    missing = [f'{bag}/{n}' for bag, n, s in files if s.encode() not in b]
    bag_named = all(bag.encode() in b for bag in e['bags'])
    good = bool(files) and not missing and bag_named
    ok += good
    rows.append({'id': e['id'], 'source_files': len(files), 'missing': missing, 'bag_path_named': bag_named, 'ok': good})
    if not good: print('BAD', e['id'], missing[:3], bag_named)
json.dump({'casefiles': len(rows), 'ok': ok, 'rows': rows}, open(sys.argv[1], 'w'), indent=1)
print(f'{ok}/{len(rows)} Case Files cite every source file by its on-disk sha256')
