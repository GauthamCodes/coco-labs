// A.2.6: score every map-the-arena drive (the 20 M3.6 submissions and the 4 reference
// drives) under Pyodide in Node, with verify.mjs's own scorer; write full metrics.
import { readFileSync, writeFileSync } from 'node:fs';
const WEB = '/home/gautham/rv3/lab_web';
const { scorer } = await import(`${WEB}/tools/verify.mjs`);
const s = await scorer();
const subs = JSON.parse(readFileSync('/home/gautham/rv3/docs/v2/data/m3/m36/submissions.json', 'utf-8')).submissions
  .filter((x) => x.challenge === 'map-the-arena').map((x, i) => ({ name: `submission_${i}`, sub: x }));
for (const lv of s.levels.challenges['map-the-arena'].levels) {
  const h = s.view('map-the-arena', lv.id).level_hash;
  for (const [name, d] of Object.entries(lv.drives)) {
    subs.push({ name: `reference_${lv.id}_${name}`, sub: { v: 1, challenge: 'map-the-arena', level: lv.id, level_hash: h, inputs: { ticks: d.ticks, log: d.inputs } } });
  }
}
const rows = subs.map(({ name, sub }) => {
  const r = s.score(sub);
  return { name, level: sub.level, hash: r.hash, stars: r.stars, metrics: Object.fromEntries(r.metrics.map((m) => [m.name, m.value])) };
});
writeFileSync(process.argv[2], JSON.stringify({ engine: s.version, subs: subs.map((x) => x.sub), rows }, null, 1));
console.log(`${rows.length} drives scored on ${s.version}`);
