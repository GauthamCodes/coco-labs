// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The 3D asset pipeline, end to end (M4.2; ADR 0006):
 *
 *   node tools/assets/build_assets.mjs           (from lab_web) write public/assets3d/ and docs/v2/ASSETS.md
 *   node tools/assets/build_assets.mjs --check   regenerate in a temporary directory; exit 1 unless every
 *                                                committed file is byte-identical and within budget
 *
 * 1. convert_world.py and convert_robot.py (Python, standard library only) make the
 *    full-resolution SOURCE GLBs from the recorded SDF world and the committed URDF;
 * 2. compress.mjs (meshoptimizer) makes the served levels of detail, meshopt-compressed;
 * 3. the ASSET MANIFEST (public/assets3d/manifest.json, and docs/v2/ASSETS.md for people):
 *    every served file's sha256, bytes, triangles, sources (each with its sha256) and
 *    licence (README §3 integrity rule 8), and the size budgets (README §5.4: the first
 *    scene 5 MB or less, the robot 1.5 MB or less), which --check enforces.
 */

import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, rmSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compressAll } from './compress.mjs';

const WEB = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const REPO = join(WEB, '..');
const OUT = join(WEB, 'public', 'assets3d');
const DOC = join(REPO, 'docs', 'v2', 'ASSETS.md');
export const BUDGET = { first_scene_bytes: 5_000_000, robot_bytes: 1_500_000 };
const OWN = "Gautham Anil's own work (COCO's CAD, Fusion 360, and its Gazebo world); Apache-2.0, the repository's licence";
const PYTHON = process.env.PYTHON ?? 'python3';

const sha = (p) => createHash('sha256').update(readFileSync(p)).digest('hex');
const rel = (p) => relative(REPO, p);

function sources() {
  const g = (...p) => join(REPO, 'gazebo_models', ...p);
  const meshes = readdirSync(g('meshes')).filter((f) => /^(base|wheel\d|m_link\d|grip\d)\.stl$/.test(f)).sort();
  return {
    robot: [g('urdf', 'coco_robo2.xacro'), join(WEB, 'tools', 'assets', 'coco_robo2.urdf'), ...meshes.map((m) => g('meshes', m))],
    arena: [g('worlds', 'coco_navigation.world'), g('urdf', 'ramp.sdf'), g('meshes', 'ramp_wedge_18.stl'),
      join(REPO, 'coco_config', 'coco_config', 'robot.py')],
  };
}

export async function build(outDir) {
  const src = mkdtempSync(join(tmpdir(), 'coco-assets-src-'));
  try {
    execFileSync(PYTHON, [join(WEB, 'tools', 'assets', 'convert_robot.py'), src], { stdio: 'pipe' });
    execFileSync(PYTHON, [join(WEB, 'tools', 'assets', 'convert_world.py'), src], { stdio: 'pipe' });
    const s = await compressAll(src, outDir);
    writeFileSync(join(outDir, 'arena.json'), readFileSync(join(src, 'arena.json')));
    const srcs = sources();
    const item = (file, kind, triangles, from, firstScene) => ({
      file, kind, bytes: readFileSync(join(outDir, file)).byteLength, sha256: sha(join(outDir, file)), triangles,
      first_scene: firstScene, licence: OWN, sources: from.map((p) => ({ path: rel(p), sha256: sha(p) })) });
    const assets = [
      item('arena.glb', 'world', s.arena.triangles, srcs.arena, 'always'),
      item('robot_high.glb', 'robot', s.levels.high.triangles, srcs.robot, 'desktop'),
      item('robot_low.glb', 'robot', s.levels.low.triangles, srcs.robot, 'phone (coarse pointer)'),
    ];
    const bytes = (f) => assets.find((a) => a.file === f).bytes;
    const manifest = {
      schema: 'lab_web.assets3d', version: '1.0', pipeline: 'docs/v2/adr/0006-asset-pipeline.md',
      tools: { meshoptimizer: JSON.parse(readFileSync(join(WEB, 'node_modules', 'meshoptimizer', 'package.json'), 'utf-8')).version,
        compression: 'EXT_meshopt_compression (codec version 0)' },
      budget: BUDGET,
      first_scene: { desktop_bytes: bytes('arena.glb') + bytes('robot_high.glb'), phone_bytes: bytes('arena.glb') + bytes('robot_low.glb') },
      levels: s.levels, assets };
    writeFileSync(join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 1) + '\n');
    return manifest;
  } finally {
    rmSync(src, { recursive: true, force: true });
  }
}

export function budgetProblems(m) {
  const out = [];
  for (const a of m.assets) if (a.kind === 'robot' && a.bytes > m.budget.robot_bytes) out.push(`${a.file}: ${a.bytes} B, over the robot's ${m.budget.robot_bytes} B`);
  for (const k of ['desktop_bytes', 'phone_bytes']) if (m.first_scene[k] > m.budget.first_scene_bytes) out.push(`first scene (${k}): ${m.first_scene[k]} B, over ${m.budget.first_scene_bytes} B`);
  for (const a of m.assets) if (!a.licence || !a.sources.length) out.push(`${a.file}: no licence or no sources`);
  return out;
}

function doc(m) {
  const kb = (b) => `${(b / 1000).toFixed(1)} kB`;
  const lines = [
    '# COCO Lab 3D assets: the manifest', '',
    'Generated by `lab_web/tools/assets/build_assets.mjs` from `lab_web/public/assets3d/manifest.json`; do not edit.',
    'Pipeline and its choices: [ADR 0006](adr/0006-asset-pipeline.md). README §3 integrity rule 8: every asset has a',
    'recorded licence; third-party assets must be CC0 or equivalent. **There are no third-party assets.**', '',
    `**Budgets** (README §5.4, checked in CI): the first scene ${kb(m.budget.first_scene_bytes)} or less, the robot ${kb(m.budget.robot_bytes)} or less.`,
    `First scene now: desktop ${kb(m.first_scene.desktop_bytes)} (arena + high robot), phone ${kb(m.first_scene.phone_bytes)} (arena + low robot).`, '',
    '| File | Kind | Bytes | sha256 | Triangles | First scene | Licence |', '|---|---|---|---|---|---|---|',
    ...m.assets.map((a) => `| \`${a.file}\` | ${a.kind} | ${a.bytes.toLocaleString('en-US')} | \`${a.sha256.slice(0, 12)}…\` | ${a.triangles.toLocaleString('en-US')} | ${a.first_scene} | ${a.licence} |`),
    '', '## Sources', '',
    ...m.assets.flatMap((a) => [`**\`${a.file}\`**`, '', ...a.sources.map((s) => `- \`${s.path}\` — \`${s.sha256.slice(0, 12)}…\``), '']),
    '## Levels of detail (the robot)', '',
    '| Level | Budget | Triangles | Per mesh: source → served |', '|---|---|---|---|',
    ...Object.entries(m.levels).map(([k, v]) => `| ${k} | ${v.budget.toLocaleString('en-US')} | ${v.triangles.toLocaleString('en-US')} | ${v.meshes.map((x) => `${x.mesh} ${x.source_tris}→${x.tris}`).join(', ')} |`),
    '',
  ];
  return lines.join('\n');
}

if (import.meta.url === `file://${process.argv[1]}`) {
  if (process.argv[2] === '--check') {
    const tmp = mkdtempSync(join(tmpdir(), 'coco-assets-check-'));
    try {
      const m = await build(tmp);
      const bad = [];
      for (const f of readdirSync(tmp)) {
        const a = readFileSync(join(tmp, f)); let b = null;
        try { b = readFileSync(join(OUT, f)); } catch { /* missing */ }
        if (!b || Buffer.compare(a, b) !== 0) bad.push(`public/assets3d/${f} is not what the pipeline makes now`);
      }
      if (readFileSync(DOC, 'utf-8') !== doc(m)) bad.push('docs/v2/ASSETS.md is not current');
      bad.push(...budgetProblems(m));
      console.log(JSON.stringify({ first_scene: m.first_scene, budget: m.budget, problems: bad }));
      process.exit(bad.length ? 1 : 0);
    } finally { rmSync(tmp, { recursive: true, force: true }); }
  } else {
    const m = await build(OUT);
    writeFileSync(DOC, doc(m));
    const p = budgetProblems(m);
    console.log(JSON.stringify({ first_scene: m.first_scene, assets: m.assets.map((a) => [a.file, a.bytes, a.triangles]), problems: p }));
    if (p.length) process.exit(1);
  }
}
