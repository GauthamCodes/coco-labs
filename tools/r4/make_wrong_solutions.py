"""Write the course's plausible wrong solutions (R4.7) as minimal edits of the references."""
import os
from pathlib import Path
R = Path('/home/gautham/coco_labs_ws/worktrees/r4/coco_lab')
F = R / 'coco_lab' / 'course' / 'files'
OUT = R / 'test' / 'course_wrong'
OUT.mkdir(exist_ok=True)
T = R / 'coco_lab' / 'templates'


def edit(src, pairs):
    for a, b in pairs:
        assert a in src, (a[:60])
        src = src.replace(a, b)
    return src


def put(ex, label, why, src):
    head = f'# R4.7 wrong solution for {ex}: {why}\n'
    (OUT / f'{ex.replace("-", "_")}__{label}.py').write_text(head + src)


UNCAUGHT = R / 'test' / 'course_wrong_uncaught'
UNCAUGHT.mkdir(exist_ok=True)


def put_uncaught(ex, label, why, src):
    """A plausible bug the check does NOT catch on its scenarios (documented, never hidden)."""
    (UNCAUGHT / f'{ex.replace("-", "_")}__{label}.py').write_text(f'# R4.7 NOT caught by {ex}: {why}\n' + src)


s = (F / 'm1_heuristic_solution.py').read_text()
oct_ = '    return max(dx, dy) + (math.sqrt(2.0) - 1.0) * min(dx, dy)'
put('m1-heuristic', 'h_zero', 'h = 0 (Dijkstra: optimal but no saving)', (F / 'm1_heuristic_starter.py').read_text())
put('m1-heuristic', 'three_octile', '3 x octile overestimates', edit(s, [(oct_, '    return 3.0 * (max(dx, dy) + (math.sqrt(2.0) - 1.0) * min(dx, dy))')]))
put('m1-heuristic', 'manhattan', 'Manhattan distance overestimates with diagonals', edit(s, [(oct_, '    return float(dx + dy)')]))

s = (F / 'm1_dijkstra_solution.py').read_text()
put('m1-dijkstra', 'starter', 'the loop left empty', (F / 'm1_dijkstra_starter.py').read_text())
put('m1-dijkstra', 'bfs_fifo', 'a FIFO queue (breadth-first search) instead of a priority queue', edit(s, [
    ('import heapq\n', 'from collections import deque\n'),
    ('    heap = [(0.0, s)]\n', '    heap = deque([(0.0, s)])\n'),
    ('        gc, cell = heapq.heappop(heap)\n', '        gc, cell = heap.popleft()\n'),
    ('                heapq.heappush(heap, (ng, nxt))\n', '                heap.append((ng, nxt))\n'),
    ('            if ng < best.get(nxt, math.inf):', '            if nxt not in best:')]))
put('m1-dijkstra', 'unit_diagonals', 'every step costs 1, diagonals included', edit(s, [('            ng = gc + step_cost(costmap, nxt, length)\n', '            ng = gc + step_cost(costmap, nxt, 1.0)\n')]))
put('m1-dijkstra', 'geometric_only', 'ignores the costmap: geometric length only', edit(s, [('            ng = gc + step_cost(costmap, nxt, length)\n', '            ng = gc + length\n')]))
put_uncaught('m1-dijkstra', 'stop_on_push', 'stops when the goal is first pushed, not when it is popped', edit(s, [(
    '                heapq.heappush(heap, (ng, nxt))\n', '                heapq.heappush(heap, (ng, nxt))\n                if nxt == g:\n                    heap = []\n                    break\n')]))

put('m1-bench', 'straight_line', 'the empty starter (a straight line)', (F / 'm1_bench_starter.py').read_text())
put('m1-bench', 'greedy', 'greedy best-first (fast, not optimal)', (T / 'planner_greedy.py').read_text())
s = (F / 'm1_bench_solution.py').read_text()
put('m1-bench', 'depth_first', 'a stack (LIFO) instead of a priority queue: depth-first, very long paths', edit(s, [
    ('        f, gc, cell = heapq.heappop(open_heap)\n', '        f, gc, cell = open_heap.pop()\n'),
    ('                heapq.heappush(open_heap, (new_g + heuristic(nxt, g), new_g, nxt))\n', '                open_heap.append((new_g + heuristic(nxt, g), new_g, nxt))\n')]))
put_uncaught('m1-bench', 'lethal_only', 'blocks only lethal cells (254), so paths clip inscribed ones', edit(s, [
    ('            if cost >= INSCRIBED_INFLATED_OBSTACLE:\n                continue                 # the robot', '            if cost >= LETHAL_OBSTACLE:\n                continue                 # the robot'),
    ('from coco_lab.api import INSCRIBED_INFLATED_OBSTACLE, Pose2D', 'from coco_lab.api import INSCRIBED_INFLATED_OBSTACLE, LETHAL_OBSTACLE, Pose2D')]))

s = (F / 'm2_inflation_solution.py').read_text()
ret = '    return int(252 * math.exp(-cost_scaling_factor * (distance - robot_radius)))'
put('m2-inflation', 'rounded', 'rounds instead of truncating', edit(s, [(ret, '    return round(252 * math.exp(-cost_scaling_factor * (distance - robot_radius)))')]))
put('m2-inflation', 'no_offset', 'forgets to subtract the robot radius', edit(s, [(ret, '    return int(252 * math.exp(-cost_scaling_factor * distance))')]))
put('m2-inflation', 'scale_253', 'scales from 253 instead of 252', edit(s, [(ret, '    return int(253 * math.exp(-cost_scaling_factor * (distance - robot_radius)))')]))
put('m2-inflation', 'strict_radius', 'distance == robot radius treated as outside', edit(s, [('    if distance <= robot_radius:', '    if distance < robot_radius:')]))

s = (F / 'm3_nogo_solution.py').read_text()
ok = '    return zone[0] <= x <= zone[2] and zone[1] <= y <= zone[3]'
put('m3-nogo', 'ignored', 'the zone ignored (the starter)', (F / 'm3_nogo_starter.py').read_text())
put('m3-nogo', 'x_only', 'only the x axis tested', edit(s, [(ok, '    return zone[0] <= x <= zone[2]')]))
put('m3-nogo', 'swapped_axes', 'x compared with the y bounds', edit(s, [(ok, '    return zone[1] <= x <= zone[3] and zone[0] <= y <= zone[2]')]))

s = (F / 'm4_lookahead_solution.py').read_text()
la = 'LOOKAHEAD = 0.45      # m'
for v in ('1.5', '2.0', '3.0'):
    put('m4-lookahead', f'lookahead_{v.replace(".", "_")}', f'lookahead {v} m cuts the corners', edit(s, [(la, f'LOOKAHEAD = {v}       # m')]))

s = (F / 'm4_goal_solution.py').read_text()
put('m4-goal', 'no_wrap', 'heading difference not wrapped', edit(s, [('    return abs(angle_diff(pose[2], goal[2])) <= yaw_tolerance', '    return abs(pose[2] - goal[2]) <= yaw_tolerance')]))
put('m4-goal', 'strict_distance', 'the boundary counted as outside', edit(s, [('    if dx * dx + dy * dy > xy_tolerance * xy_tolerance:', '    if dx * dx + dy * dy >= xy_tolerance * xy_tolerance:')]))
put('m4-goal', 'no_yaw', 'heading ignored', edit(s, [('    return abs(angle_diff(pose[2], goal[2])) <= yaw_tolerance', '    return True')]))
put('m4-goal', 'manhattan', 'Manhattan distance instead of Euclidean', edit(s, [('    if dx * dx + dy * dy > xy_tolerance * xy_tolerance:', '    if abs(dx) + abs(dy) > xy_tolerance:')]))

s = (F / 'm5_resample_solution.py').read_text()
body = s[s.index('    n = len(particles)'):]
put('m5-resample', 'identity', 'keeps every particle once (the starter)', (F / 'm5_resample_starter.py').read_text())
put('m5-resample', 'uniform', 'picks particles uniformly, ignoring the weights', s.replace(body, '    n = len(particles)\n    return [particles[int(rng.random() * n)] for _ in range(n)]\n'))
put('m5-resample', 'argmax', 'copies only the best particle', s.replace(body, '    best = max(range(len(weights)), key=lambda i: weights[i])\n    return [particles[best]] * len(particles)\n'))
put('m5-resample', 'off_by_one', 'steps by 1/(N-1), overshooting the weights', edit(s, [('    step = 1.0 / n\n', '    step = 1.0 / (n - 1)\n')]))

s = (F / 'm6_logodds_solution.py').read_text()
body = s[s.index('    for hit in hits:'):]
put('m6-logodds', 'clamp_at_end', 'clamps once at the end', s.replace(body, '    for hit in hits:\n        l += L_OCC if hit else L_FREE\n    return max(L_MIN, min(L_MAX, l))\n'))
put('m6-logodds', 'no_clamp', 'never clamps', s.replace(body, '    for hit in hits:\n        l += L_OCC if hit else L_FREE\n    return l\n'))
put('m6-logodds', 'swapped', 'adds L_FREE for a hit and L_OCC for a pass', edit(s, [('        l += L_OCC if hit else L_FREE\n', '        l += L_FREE if hit else L_OCC\n')]))

put('m10-export', 'straight_line', 'a straight-line planner that fails here first', (T / 'planner_empty.py').read_text())
put('m10-export', 'imports_os', 'imports os (the guard refuses it)', 'import os\n' + (F / 'm10_export_solution.py').read_text())
put('m10-export', 'syntax_error', 'a syntax error', (F / 'm10_export_solution.py').read_text().replace('def plan(costmap, start, goal, ctx):', 'def plan(costmap, start, goal, ctx)'))
print(sorted(os.listdir(OUT)))
