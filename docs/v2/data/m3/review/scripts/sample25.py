"""A.2.5: a stratified sample of 25 of M3.6's 100 committed submissions: 5 per
challenge, every 4th within each challenge (so every level is likely covered,
and the 7 deliberately invalid ones are included where they fall)."""
import json, collections
D = '/home/gautham/rv3/docs/v2/data/m3/m36'
subs = json.load(open(f'{D}/submissions.json'))
rows = subs['submissions']
by = collections.defaultdict(list)
for i, s in enumerate(rows): by[s['challenge']].append(i)
pick = []
for c, idx in by.items():
    step = max(1, len(idx) // 5)
    pick += idx[::step][:5]
out = dict(subs, submissions=[rows[i] for i in pick], sampled_from='docs/v2/data/m3/m36/submissions.json', indices=pick)
json.dump(out, open('/home/gautham/review/m3_tmp/subs25.json', 'w'), indent=1)
print(len(pick), collections.Counter(rows[i]['challenge'] for i in pick), pick)
