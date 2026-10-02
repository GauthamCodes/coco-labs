"""Analyse a fetch run: state sequence, result, recoveries, publishers."""
import json
import sys

for run in sys.argv[1:]:
    ws = [json.loads(line) for line in open(f'{run}/ws.jsonl')]
    ros = [json.loads(line) for line in open(f'{run}/ros.jsonl')]
    seen = []
    for r in ros:
        if r['topic'] == '/mission/state':
            s = r['data'].split(' ')[0].split('=')[1]
            if not seen or seen[-1] != s:
                seen.append(s)
    end = [r for r in ws if r['kind'] == 'phase' and r['name'] == 'end']
    loc = [r for r in ws if r['kind'] == 'localised_after']
    print('==', run.rsplit('/', 1)[-1])
    print(' > '.join(seen))
    print('end', end[-1] if end else None)
    print('localised_after_s', loc[0]['s'] if loc else None,
          'RECOVERY entries', seen.count('RECOVERY'),
          'RELOCALIZE entries', seen.count('RELOCALIZE'))
    t0 = next((r['t'] for r in ws if r['kind'] == 'tx'
               and r['frame']['type'] == 'mission'), None)
    if end and t0:
        print('wall s start->end', round(end[-1]['t'] - t0, 1))
    pc = {(r['wheel'], tuple(r['names'])) for r in ros
          if r['topic'] == 'pubcount'}
    print('wheel publishers', sorted(pc))
