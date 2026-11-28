// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/*
 * R6.A3: is the gateway's robot.truth in the level's map frame? A test route, from outside the container.
 *
 *   node docker/coco-ros2/truth_route.mjs ws://127.0.0.1:8766/ws OUT.json --container coco --w2m 0,0
 *
 * Drives a short Nav2 route through the gateway (coco.v1 nav_goal: 1.2 m ahead, then 1.0 m to the left,
 * then back to the start) and, at every stop (the goal succeeded and COCO has stood still 1.5 s), samples
 * three poses: the gateway's robot.truth (what the browser shows as truth), the gateway's robot.pose (the
 * AMCL estimate), and Gazebo's OWN world pose of the model, read independently in the container
 * (`gz model -m coco -p`) and put in the map frame with the level's world_to_map (map = world + w2m).
 * Moving samples are recorded too, but only stops are judged (the three reads are ~0.1-1 s apart).
 *
 * Pass: every stop (start + 3 legs) has a stationary sample (Gazebo's pose moved < 1 cm since the previous
 * sample of that stop), and at every stationary sample |truth - Gazebo| <= 0.05 m. The truth-vs-estimate distance at each stop is reported
 * as measured (it is what the site would show), not judged. Evidence class: LIVE (a Gazebo simulation).
 */
import { execFile, execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';

const [url, out, ...rest] = process.argv.slice(2);
const arg = (k, d) => (rest.includes(k) ? rest[rest.indexOf(k) + 1] : d);
const container = arg('--container', 'coco');
const w2m = arg('--w2m', '0,0').split(',').map(Number);
const TOL = 0.05;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rec = { schema: 'coco_ros2.truth_route', version: 1, url, utc: new Date().toISOString(), world_to_map: w2m,
  tolerance_m: TOL, stops: [], moving: [], goals: [], errors: [] };

function gzPose() {
  return new Promise((resolve) => {
    const t0 = Date.now();
    // gz is ROS's vendored Gazebo: on PATH only after sourcing setup.bash (as the entrypoint does)
    execFile('docker', ['exec', container, 'bash', '-c', 'source /opt/ros/jazzy/setup.bash >/dev/null 2>&1; gz model -m coco -p'], { timeout: 8000 }, (err, stdout) => {
      const raw = String(stdout ?? '');
      // `gz model -p`: the XYZ triple is the first bracketed group of three numbers after "XYZ"
      const after = raw.slice(Math.max(0, raw.indexOf('XYZ')));
      const groups = [...after.matchAll(/\[([^\]]+)\]/g)].map((m) => m[1].trim().split(/\s+/).map(Number))
        .filter((g) => g.length === 3 && g.every(Number.isFinite));
      const xyz = groups[0] ?? null;
      resolve({ ms: [t0, Date.now()], raw: raw.slice(0, 400), error: err ? String(err.message).slice(0, 200) : null,
        world: xyz, map: xyz ? [xyz[0] + w2m[0], xyz[1] + w2m[1]] : null });
    });
  });
}
const d = (a, b) => (a && b ? Math.hypot(a[0] - b[0], a[1] - b[1]) : null);

let last = null; let code = 1;
try {
  const controlCode = execFileSync('docker', ['exec', container, 'cat', '/tmp/coco/control_code'], { encoding: 'utf-8' }).trim();
  const ws = new WebSocket(url);
  const acks = new Map(); let nextId = 1;
  const send = (f) => { const id = nextId++; ws.send(JSON.stringify({ ...f, id })); return id; };
  const answered = async (id, ms = 3000) => { const t0 = Date.now(); while (!acks.has(id) && Date.now() - t0 < ms) await sleep(50); return acks.get(id) ?? null; };
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = () => reject(new Error(`could not open ${url}`)); });
  ws.onmessage = (ev) => {
    if (typeof ev.data !== 'string') return;
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.type === 'telemetry') last = m;
    else if (m.type === 'welcome') rec.welcome_config = m.config ?? null;
    else if (m.type === 'ack' || m.type === 'error') acks.set(m.id, m);
  };
  send({ type: 'hello', client: 'coco-ros2 truth_route', binary: false });
  for (let i = 0; i < 100 && !last?.robot?.truth; i++) await sleep(100);
  rec.claim = (await answered(send({ type: 'claim', code: controlCode })))?.type ?? null;
  rec.set_mode = (await answered(send({ type: 'set_mode', mode: 'auto' })))?.type ?? null;
  await sleep(1500);

  const snap = async (label) => {
    const g = await gzPose();
    const truth = last?.robot?.truth ? [last.robot.truth.x, last.robot.truth.y] : null;
    const est = last?.robot?.pose ? [last.robot.pose.x, last.robot.pose.y] : null;
    return { label, t_ms: Date.now(), truth, estimate: est, gazebo_world: g.world, gazebo_map: g.map,
      truth_vs_gazebo_m: d(truth, g.map), truth_vs_estimate_m: d(truth, est), speed: last?.robot?.velocity?.linear ?? null,
      gz_error: g.error, gz_raw: rec.stops.length === 0 && label === 'start' ? g.raw : undefined };
  };
  // a sample is judged only if COCO is standing still: Gazebo's pose moved < 1 cm since the previous sample of
  // the same stop (CI run 46108505274: the first 'start' sample was taken while COCO still rolled 0.08 m)
  const stop = async (label) => {
    await sleep(1500);
    let prev = null;
    for (let k = 0; k < 4; k++) {
      const x = await snap(`${label}#${k}`);
      x.stationary = prev !== null && d(prev, x.gazebo_map) !== null && d(prev, x.gazebo_map) < 0.01;
      prev = x.gazebo_map;
      rec.stops.push(x);
      await sleep(300);
    }
  };

  await stop('start');
  const p0 = last?.robot?.pose;
  if (!p0) throw new Error('no AMCL pose from the gateway');
  const c = Math.cos(p0.yaw), s = Math.sin(p0.yaw);
  const route = [[p0.x + 1.2 * c, p0.y + 1.2 * s], [p0.x + 1.2 * c - 1.0 * s, p0.y + 1.2 * s + 1.0 * c], [p0.x, p0.y]];
  for (const [k, [gx, gy]] of route.entries()) {
    const sent = Date.now();
    const ack = await answered(send({ type: 'nav_goal', x: gx, y: gy }));
    let status = null;
    for (let i = 0; i < 600; i++) {                       // up to 60 s per leg; a moving sample every ~1 s
      await sleep(100);
      status = last?.nav?.goal?.status ?? null;
      if (i % 10 === 5) rec.moving.push(await snap(`leg${k + 1}`));
      if (Date.now() - sent > 2000 && ['succeeded', 'aborted', 'canceled'].includes(status)) break;
    }
    rec.goals.push({ leg: k + 1, goal: [gx, gy], ack: ack?.type ?? null, status, seconds: (Date.now() - sent) / 1000 });
    await stop(`after_leg${k + 1}`);
  }
  await answered(send({ type: 'stop' }));
  ws.close();

  const judged = rec.stops.filter((x) => x.stationary && x.truth_vs_gazebo_m !== null);
  rec.judged_samples = judged.length;
  rec.stops_with_a_judged_sample = new Set(judged.map((x) => x.label.split('#')[0])).size;
  rec.max_stop_truth_vs_gazebo_m = judged.length ? Math.max(...judged.map((x) => x.truth_vs_gazebo_m)) : null;
  rec.max_stop_truth_vs_estimate_m = judged.length ? Math.max(...judged.map((x) => x.truth_vs_estimate_m ?? 0)) : null;
  rec.max_moving_truth_vs_gazebo_m = Math.max(...rec.moving.filter((x) => x.truth_vs_gazebo_m !== null).map((x) => x.truth_vs_gazebo_m), 0);
  rec.legs_succeeded = rec.goals.filter((g) => g.status === 'succeeded').length;
  // the gateway must say so too: the site shows truth-vs-estimate only for truth_frame 'level_map'
  rec.truth_frame = rec.welcome_config?.truth_frame ?? null;
  rec.pass = rec.stops_with_a_judged_sample === 4 && rec.max_stop_truth_vs_gazebo_m <= TOL
    && rec.truth_frame === 'level_map';
  code = rec.pass ? 0 : 1;
} catch (e) {
  rec.errors.push(String(e?.message ?? e));
  rec.pass = false;
}
writeFileSync(out, JSON.stringify(rec, null, 1) + '\n');
console.log(JSON.stringify({ pass: rec.pass, truth_frame: rec.truth_frame, max_stop_truth_vs_gazebo_m: rec.max_stop_truth_vs_gazebo_m,
  max_stop_truth_vs_estimate_m: rec.max_stop_truth_vs_estimate_m, legs_succeeded: rec.legs_succeeded, errors: rec.errors }));
process.exit(code);
