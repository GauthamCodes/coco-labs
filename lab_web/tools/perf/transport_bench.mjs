// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M1.1 / ADR 0001: how should search events cross from Python (Pyodide) to
 * JavaScript? Measured in Pyodide-in-Node on one real coco_lab trace.
 *
 *   node tools/perf/transport_bench.mjs [--size 220] [--reps 7] [--out FILE]
 *
 * The trace: coco_lab's own Dijkstra on a seeded size x size grid (20 %
 * blocked, 8-connected), run inside Pyodide. Each variant moves the SAME
 * trace columns (kind, row, col, sub, g, h, f, parent_*), plus the three
 * clocks every event carries (seq, tick, t_world), into JavaScript:
 *
 *   A  columnar typed arrays: Python `array` per column -> getBuffer()
 *      -> a copied, transferable JS typed array. No dependency.
 *   B  protobuf in Python, columnar (packed repeated fields, one message per
 *      batch), SerializeToString -> bytes -> JS Uint8Array. Needs the
 *      Pyodide `protobuf` package.
 *   C  protobuf in Python, one sub-message per event (row-wise).
 *   D  JS-side storage encode of A's arrays into the same packed protobuf
 *      bytes as B (@bufbuild/protobuf BinaryWriter); B and D bytes must be
 *      identical, which the run checks.
 *
 * Every timing is wall-clock, median of --reps, after one warm-up. Nothing
 * here is shipped to the site.
 */

import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';
import { BinaryWriter, WireType } from '@bufbuild/protobuf/wire';
import { loadPyodide, version as pyodideVersion } from 'pyodide';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SIZE = Number(args.size ?? 220);
const REPS = Number(args.reps ?? 7);
const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..', '..', '..');
const median = (xs) => { const s = [...xs].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const r1 = (x) => Math.round(x * 10) / 10;

// Field order = protobuf field numbers 1..13 (B, C and D share it).
const INT_COLS = ['kind', 'row', 'col', 'sub', 'parent_row', 'parent_col', 'parent_sub'];
const FLOAT_COLS = ['g', 'h', 'f'];
const FIELDS = [['seq', 'u64'], ['tick', 'u64'], ['t_world', 'f64'],
  ...INT_COLS.map((c) => [c, 'i32']), ...FLOAT_COLS.map((c) => [c, 'f64'])];

const t0 = performance.now();
const py = await loadPyodide({ indexURL: join(repo, 'lab_web', 'node_modules', 'pyodide') + '/' });
const loadPyodideMs = performance.now() - t0;

// coco_lab, from this checkout, into Pyodide's file system.
const src = join(repo, 'coco_lab', 'coco_lab');
const walk = (d) => readdirSync(d).flatMap((n) => { const p = join(d, n); return statSync(p).isDirectory() ? walk(p) : [p]; });
for (const f of walk(src).filter((p) => p.endsWith('.py') || p.endsWith('.json'))) {
  const dst = `/home/pyodide/coco_lab/${relative(src, f)}`;
  py.FS.mkdirTree(dirname(dst));
  py.FS.writeFile(dst, readFileSync(f));
}

py.runPython(`
import random, sys, time
from array import array
sys.path.insert(0, '/home/pyodide')
from coco_lab.grid import Grid
from coco_lab.search import search
SIZE = ${SIZE}
rng = random.Random(7)
blocked = [rng.random() < 0.2 for _ in range(SIZE * SIZE)]
for r in range(3):  # free 3 x 3 corners, so the start is never walled in
    for c in range(3):
        blocked[r * SIZE + c] = False
        blocked[(SIZE - 1 - r) * SIZE + (SIZE - 1 - c)] = False
grid = Grid(SIZE, SIZE, blocked)
t = time.perf_counter()
result = search(grid, (0, 0), (SIZE - 1, SIZE - 1), 'dijkstra')
SEARCH_MS = (time.perf_counter() - t) * 1000
COLS = result.trace.events
N = len(COLS['kind'])
# the three clocks every event carries (one planning call: one tick)
COLS = dict(COLS, seq=list(range(N)), tick=[0] * N, t_world=[0.0] * N)
INT_COLS = ${JSON.stringify(INT_COLS)}
FLOAT_COLS = ${JSON.stringify(FLOAT_COLS)}

def columnar():
    out = {'seq': array('Q', COLS['seq']), 'tick': array('Q', COLS['tick']),
           't_world': array('d', COLS['t_world'])}
    for c in INT_COLS:
        out[c] = array('i', COLS[c])
    for c in FLOAT_COLS:
        out[c] = array('d', COLS[c])
    return out
`);
const n = py.globals.get('N');
const searchMs = py.globals.get('SEARCH_MS');

// -- A: columnar typed arrays -------------------------------------------
const columnarPy = py.globals.get('columnar');
function variantA() {
  const tPy = performance.now();
  const d = columnarPy();
  const pyMs = performance.now() - tPy;
  const tJs = performance.now();
  const out = {};
  for (const [name] of FIELDS) {
    const arr = d.get(name);
    const buf = arr.getBuffer();
    out[name] = buf.data.slice(); // a copy the worker can transfer
    buf.release();
    arr.destroy();
  }
  d.destroy();
  return { out, pyMs, jsMs: performance.now() - tJs };
}

// -- D: JS-side protobuf encode of A's arrays ---------------------------
function encodeD(cols) {
  const w = new BinaryWriter();
  FIELDS.forEach(([name, type], i) => {
    const a = cols[name];
    w.tag(i + 1, WireType.LengthDelimited).fork();
    if (type === 'u64') for (let k = 0; k < a.length; k += 1) w.uint64(a[k]);
    else if (type === 'i32') for (let k = 0; k < a.length; k += 1) w.int32(a[k]);
    else for (let k = 0; k < a.length; k += 1) w.double(a[k]);
    w.join();
  });
  return w.finish();
}

// -- B / C: protobuf inside Python --------------------------------------
const tPb = performance.now();
await py.loadPackage('protobuf', { messageCallback: () => {} });
const loadProtobufMs = performance.now() - tPb;
const tImp = performance.now();
py.runPython(`
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
import google.protobuf
PB_VERSION = google.protobuf.__version__
from google.protobuf.internal import api_implementation
PB_IMPL = api_implementation.Type()
`);
const importProtobufMs = performance.now() - tImp;
py.runPython(`
FDP = descriptor_pb2.FieldDescriptorProto
TYPES = {'u64': FDP.TYPE_UINT64, 'i32': FDP.TYPE_INT32, 'f64': FDP.TYPE_DOUBLE}
FIELDS = ${JSON.stringify(FIELDS)}
fdp = descriptor_pb2.FileDescriptorProto(name='bench.proto', package='bench', syntax='proto3')
batch = fdp.message_type.add(name='Batch')
event = fdp.message_type.add(name='Event')
rows = fdp.message_type.add(name='Rows')
for i, (name, typ) in enumerate(FIELDS, 1):
    batch.field.add(name=name, number=i, type=TYPES[typ], label=FDP.LABEL_REPEATED)
    event.field.add(name=name, number=i, type=TYPES[typ], label=FDP.LABEL_OPTIONAL)
rows.field.add(name='events', number=1, type=FDP.TYPE_MESSAGE, label=FDP.LABEL_REPEATED,
               type_name='.bench.Event')
pool = descriptor_pool.DescriptorPool()
pool.Add(fdp)
get = getattr(message_factory, 'GetMessageClass', None)
Batch = get(pool.FindMessageTypeByName('bench.Batch'))
Rows = get(pool.FindMessageTypeByName('bench.Rows'))
NAMES = [f[0] for f in FIELDS]

def variant_b():
    m = Batch()
    for name in NAMES:
        getattr(m, name).extend(COLS[name])
    return m.SerializeToString()

def variant_c():
    m = Rows()
    cols = [COLS[name] for name in NAMES]
    add = m.events.add
    for k in range(N):
        e = add()
        for name, col in zip(NAMES, cols):
            setattr(e, name, col[k])
    return m.SerializeToString()
`);
const bPy = py.globals.get('variant_b');
const cPy = py.globals.get('variant_c');
function variantBytes(fn) {
  const tPy = performance.now();
  const bytes = fn();
  const pyMs = performance.now() - tPy;
  const tJs = performance.now();
  const u8 = bytes.toJs();
  bytes.destroy();
  return { u8, pyMs, jsMs: performance.now() - tJs };
}

function measure(fn) {
  fn(); // warm-up
  const runs = [];
  for (let i = 0; i < REPS; i += 1) runs.push(fn());
  return runs;
}

const A = measure(variantA);
const D = measure(() => { const a = variantA(); const t = performance.now(); const u8 = encodeD(a.out); return { u8, jsMs: performance.now() - t }; });
const B = measure(() => variantBytes(bPy));
const C = measure(() => variantBytes(cPy));
const identical = Buffer.compare(Buffer.from(B[0].u8), Buffer.from(D[0].u8)) === 0;
const aBytes = Object.values(A[0].out).reduce((s, a) => s + a.byteLength, 0);

const summary = (runs, key) => ({ median_ms: r1(median(runs.map((r) => r[key]))), min_ms: r1(Math.min(...runs.map((r) => r[key]))), max_ms: r1(Math.max(...runs.map((r) => r[key]))) });
const result = {
  meta: {
    at_utc: new Date().toISOString(), node: process.version, pyodide: pyodideVersion,
    protobuf_python: py.globals.get('PB_VERSION'), protobuf_impl: py.globals.get('PB_IMPL'),
    cpu: os.cpus()[0].model, cores: os.cpus().length, load1: r1(os.loadavg()[0]), reps: REPS,
    workload: `coco_lab dijkstra, ${SIZE}x${SIZE} grid, 20% blocked (random.Random(7)), 8-connected, (0,0)->(${SIZE - 1},${SIZE - 1})`,
  },
  events: n, search_ms_in_pyodide: r1(searchMs),
  load_pyodide_ms: r1(loadPyodideMs), load_protobuf_package_ms: r1(loadProtobufMs), import_protobuf_ms: r1(importProtobufMs),
  A_columnar: { python: summary(A, 'pyMs'), to_js: summary(A, 'jsMs'), bytes: aBytes },
  B_protobuf_columnar_in_python: { python: summary(B, 'pyMs'), to_js: summary(B, 'jsMs'), bytes: B[0].u8.byteLength },
  C_protobuf_rowwise_in_python: { python: summary(C, 'pyMs'), to_js: summary(C, 'jsMs'), bytes: C[0].u8.byteLength },
  D_js_encode_of_A: { js: summary(D, 'jsMs'), bytes: D[0].u8.byteLength, identical_to_B: identical },
};
console.log(JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...result }, null, 1));
if (args.out) writeFileSync(args.out, JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...result }, null, 1) + '\n');
