// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Every level's reference answer, scored under Pyodide (M3.6):
 *
 *   node tools/play_reference_check.mjs [--out FILE.json]      (from lab_web, after npm run arena-assets)
 *
 * The star thresholds are computed in CPython (make_play_levels.py); the
 * page and `coco verify` score in Pyodide. This replays each reference the
 * level publishes, under Pyodide, and requires the stars it was meant to
 * earn: A*'s path, A*'s expansions, the optimal order, the divergence tick
 * -- 3 stars; each map level's two reference drives -- 1 star for the weaker,
 * 3 for the stronger, with F1 exactly the committed reference and ATE
 * within coco_lab.play.MAP_ATE_EPS of it. Exits 1 on any miss.
 */

import { writeFileSync } from 'node:fs';
import { scorer } from './verify.mjs';

const opt = (k) => { const i = process.argv.indexOf(k); return i >= 0 ? process.argv[i + 1] : null; };
const s = await scorer();
const L = s.levels.challenges;
const rows = [];
const sub = (challenge, level, inputs) => ({ v: 1, challenge, level, level_hash: s.view(challenge, level).level_hash, inputs });
const check = (challenge, level, what, inputs, want, extra = () => null) => {
  const r = s.score(sub(challenge, level, inputs));
  const why = r.stars !== want ? `${r.stars} stars, not ${want}` : extra(r);
  rows.push({ challenge, level, what, stars: r.stars, want, ok: !why, why });
  console.log(`${why ? 'MISS' : 'ok  '} ${challenge}/${level} ${what}: ${r.stars} stars${why ? ` (${why})` : ''}`);
};

for (const lv of L['beat-the-planner'].levels) check('beat-the-planner', lv.id, "A*'s path", s.view('beat-the-planner', lv.id).optimal_path, 3);
for (const lv of L['next-node'].levels) check('next-node', lv.id, "A*'s expansions", s.view('next-node', lv.id).frames.map((f) => f.expanded), 3);
for (const lv of L['search-the-bays'].levels) check('search-the-bays', lv.id, 'the optimal order', lv.reference.optimal_order, 3);
for (const lv of L['case-file-detective'].levels) check('case-file-detective', lv.id, 'the divergence tick', [lv.moment.tick], 3);
const ATE_EPS = 1e-6; // coco_lab.play.MAP_ATE_EPS
for (const lv of L['map-the-arena'].levels) {
  const [weak, strong] = ['out_and_back', 'tour'].sort((a, b) => lv.reference[a].f1 - lv.reference[b].f1);
  for (const [name, want] of [[weak, 1], [strong, 3]]) {
    const d = lv.drives[name];
    check('map-the-arena', lv.id, `the ${name} drive`, { ticks: d.ticks, log: d.inputs }, want, (r) => {
      const m = Object.fromEntries(r.metrics.map((x) => [x.name, x.value]));
      if (m.f1 !== lv.reference[name].f1) return `F1 ${m.f1} is not the committed ${lv.reference[name].f1}`;
      if (Math.abs(m.ate - lv.reference[name].ate) > ATE_EPS) return `ATE ${m.ate} is not within ${ATE_EPS} m of ${lv.reference[name].ate}`;
      return null;
    });
  }
}
const out = { tool: 'lab_web/tools/play_reference_check.mjs', engine: s.version, ok: rows.every((r) => r.ok), rows };
if (opt('--out')) writeFileSync(opt('--out'), JSON.stringify(out, null, 1) + '\n');
console.log(`${rows.filter((r) => r.ok).length} of ${rows.length} references earn their stars under ${s.version}`);
process.exit(out.ok ? 0 : 1);
