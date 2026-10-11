"""Summarise the D6 layout comparison: per Case File, the median of 3 rounds per layout."""
import json, statistics, sys
B = '/home/gautham/review/m3_tmp/d6_compare'
rows, out = {}, {'what': 'D6 layout comparison: first frame (and, for split/ordered, scans ready) on emulated 4G '
                 '(9 Mbit/s down, 1.5 up, 170 ms), 12 Case Files, 3 interleaved rounds per layout, GPU, balanced, AC',
                 'layouts': {}}
for lay in ('m3', 'split', 'ordered'):
    per = {}
    for r in (1, 2, 3):
        d = json.load(open(f'{B}/{lay}/round_{r}/casefile_check_4g.json'))
        if r == 1: out['layouts'][lay] = {'conditions_round_1': d['conditions']}
        for c in d['casefiles']:
            p = per.setdefault(c['id'], {'bytes': c['bytes'], 'first': [], 'scans': [], 'errors': 0, 'ok': True})
            p['first'].append(c['first_frame_ms']); p['scans'].append(c.get('scans_ms'))
            p['errors'] += len(c['errors']); p['ok'] &= c['ok']
    for i, p in per.items():
        rows.setdefault(i, {})[lay] = {'first_ms_median': round(statistics.median(p['first']), 1),
                                       'first_ms_rounds': [round(x, 1) for x in p['first']],
                                       'scans_ms_median': round(statistics.median(p['scans']), 1) if None not in p['scans'] else None,
                                       'errors': p['errors'], 'ok': p['ok']}
    fm = [statistics.median(p['first']) for p in per.values()]
    out['layouts'][lay].update({'first_ms_max_of_medians': round(max(fm), 1), 'first_ms_median_of_medians': round(statistics.median(fm), 1),
                                'within_2s': sum(x <= 2000 for x in fm), 'casefiles': len(fm), 'errors': sum(p['errors'] for p in per.values())})
    if lay != 'm3':
        sm = [statistics.median(p['scans']) for p in per.values()]
        out['layouts'][lay]['scans_ms_max_of_medians'] = round(max(sm), 1)
out['casefiles'] = rows
json.dump(out, open(sys.argv[1], 'w'), indent=1)
for lay, v in out['layouts'].items(): print(lay, {k: v[k] for k in v if k != 'conditions_round_1'})
print(f"{'case file':32s} {'m3':>8s} {'split':>8s} {'ordered':>8s}")
for i, r in sorted(rows.items(), key=lambda kv: -kv[1]['m3']['first_ms_median']):
    print(f"{i:32s} {r['m3']['first_ms_median']:8.0f} {r['split']['first_ms_median']:8.0f} {r['ordered']['first_ms_median']:8.0f}")
