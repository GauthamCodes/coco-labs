"""A.2.4: recompute challenge star thresholds independently of make_play_levels.py.
Beat the planner: own Dijkstra (8-connected, no corner cutting, move = length * (1 + 2c/252)).
Search the bays: own expected cost over all permutations, own nearest-first and
most-likely-first (Bayes update on a miss). Compared with levels.json's reference."""
import heapq, itertools, json, math, sys
L = json.load(open('/home/gautham/rv3/lab_web/play/levels.json'))
out = {}

def dijkstra(rows):
    H, W = len(rows), len(rows[0])
    S = G = None
    for r, line in enumerate(rows):
        for c, ch in enumerate(line):
            if ch == 'S': S = (r, c)
            if ch == 'G': G = (r, c)
    def free(r, c): return 0 <= r < H and 0 <= c < W and rows[r][c] != '#'
    def cost(r, c): ch = rows[r][c]; return int(ch) * 28.0 if ch.isdigit() else 0.0
    dist = {S: 0.0}; pq = [(0.0, S)]
    while pq:
        d, (r, c) = heapq.heappop(pq)
        if (r, c) == G: return d
        if d > dist[(r, c)]: continue
        for dr, dc in itertools.product((-1, 0, 1), repeat=2):
            if (dr, dc) == (0, 0): continue
            nr, nc = r + dr, c + dc
            if not free(nr, nc): continue
            if dr and dc and not (free(r + dr, c) and free(r, c + dc)): continue
            nd = d + math.hypot(dr, dc) * (1 + 2 * cost(nr, nc) / 252)
            if nd < dist.get((nr, nc), math.inf):
                dist[(nr, nc)] = nd; heapq.heappush(pq, (nd, (nr, nc)))

def ecost(p, prior, order):
    at, tot, ps, cs = p['start'], 0.0, [], []
    for i in order:
        rg = p['regions'][i]
        tot += p['travel'][at][rg['id']] + rg['survey_cost']
        cs.append(tot); ps.append(prior[i] * p['detection'][i]); at = rg['id']
    return math.fsum(a * b for a, b in zip(ps, cs)) + max(0.0, 1 - math.fsum(ps)) * tot

def policy(p, kind):
    bel = list(p['prior']); at = p['start']; left = list(range(len(bel))); order = []
    while left:
        if kind == 'nearest':
            nxt = min(left, key=lambda i: (p['travel'][at][p['regions'][i]['id']] + p['regions'][i]['survey_cost'], i))
        else:
            nxt = max(left, key=lambda i: (bel[i], -i))
        order.append(nxt); left.remove(nxt)
        d = p['detection'][nxt]; z = 1 - bel[nxt] * d
        bel = [b * (1 - d) / z if j == nxt else b / z for j, b in enumerate(bel)]
        at = p['regions'][nxt]['id']
    return order

ok = total = 0
for lv in L['challenges']['beat-the-planner']['levels']:
    mine = dijkstra(lv['grid']); ref = lv['reference']['optimal_cost']
    good = abs(mine - ref) < 1e-6; ok += good; total += 1
    out[f"beat/{lv['id']}"] = {'optimal_mine': round(mine, 9), 'optimal_ref': ref, 'match': good}
for lv in L['challenges']['search-the-bays']['levels']:
    p = lv['problem']; prior = p['prior']; n = len(prior)
    best = min(ecost(p, prior, o) for o in itertools.permutations(range(n)))
    ref = lv['reference']
    r_near = ecost(p, prior, policy(p, 'nearest')) / best
    r_ml = ecost(p, prior, policy(p, 'most_likely')) / best
    good = (abs(best - ref['optimal_expected']) < 1e-6 and abs(r_near - ref['nearest_ratio']) < 1e-6
            and abs(r_ml - ref['most_likely_ratio']) < 1e-6)
    ok += good; total += 1
    out[f"bays/{lv['id']}"] = {'optimal_mine': round(best, 9), 'optimal_ref': ref['optimal_expected'],
                               'nearest_mine': round(r_near, 9), 'nearest_ref': ref['nearest_ratio'],
                               'most_likely_mine': round(r_ml, 9), 'most_likely_ref': ref['most_likely_ratio'],
                               'match': good}
for k, v in out.items(): print(('OK ' if v['match'] else 'BAD'), k, v)
print(f'{ok}/{total} levels recomputed independently match')
json.dump({'ok': ok, 'total': total, 'levels': out}, open(sys.argv[1], 'w'), indent=1)
