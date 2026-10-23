/**
 * M6F.4: the Depot planning benchmark in Pyodide-in-Node (bench_planning.py's run()).
 *
 *   node tools/m6/bench_planning_pyodide.mjs --pyodide DIR --spec-json FILE --out FILE
 *        [--repeats 5]
 *
 * DIR is an installed `pyodide` npm package at lab_web's pinned version
 * (lab_web/package.json: 314.0.7), e.g. `npm install pyodide@314.0.7 --prefix P`
 * then DIR = P/node_modules/pyodide. coco_lab and bench_planning.py are copied
 * from this checkout into Pyodide's file system, as lab_web/tools/perf/arena_node.mjs
 * does; nothing else is fetched. FILE is the spec as JSON
 * (bench_planning.py --write-json).
 */

import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import os from 'node:os';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..', '..');

const { loadPyodide, version } = await import(pathToFileURL(join(args.pyodide, 'pyodide.mjs')).href);
const t0 = performance.now();
const py = await loadPyodide({ indexURL: args.pyodide + '/' });
const loadMs = performance.now() - t0;
const src = join(repo, 'coco_lab', 'coco_lab');
const walk = (d) => readdirSync(d).flatMap((n) => {
  const p = join(d, n);
  return statSync(p).isDirectory() ? walk(p) : [p];
});
for (const f of walk(src).filter((p) => /\.(py|json)$/.test(p))) {
  const dst = `/home/pyodide/coco_lab/${relative(src, f)}`;
  py.FS.mkdirTree(dirname(dst));
  py.FS.writeFile(dst, readFileSync(f));
}
py.FS.writeFile('/home/pyodide/bench_planning.py', readFileSync(join(here, 'bench_planning.py')));
py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')");
py.globals.set('SPEC_JSON', readFileSync(args['spec-json'], 'utf-8'));
py.globals.set('REPEATS', Number(args.repeats ?? 5));
const loadavgBefore = os.loadavg();
const text = py.runPython(`
import json, bench_planning
json.dumps(bench_planning.run(json.loads(SPEC_JSON), REPEATS))
`);
const result = JSON.parse(text);
Object.assign(result, {
  engine: 'pyodide-node', pyodide: version, node: process.version, pyodide_load_ms: loadMs,
  budget_warm_ms: 300,
  conditions: { load_average_before: loadavgBefore, load_average_after: os.loadavg(),
    cpu: os.cpus()[0].model, nproc: os.cpus().length, platform: `${os.type()} ${os.release()}` },
});
writeFileSync(args.out, JSON.stringify(result, null, 1) + '\n');
for (const r of result.results) {
  console.log(`${r.pair.padEnd(28)} ${r.planner.padEnd(15)} found=${r.found} ` +
    `cold=${r.cold_ms.toFixed(1)} warm=${r.warm_median_ms.toFixed(1)}`);
}
