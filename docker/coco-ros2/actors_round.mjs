// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/*
 * R6.A4: the Depot's actors move, and stop for COCO, in the coco-ros2 image: one Depot round.
 *
 *   node docker/coco-ros2/actors_round.mjs ws://127.0.0.1:8766/ws OUT.json --container coco
 *
 * The round is G2.9's own actor-yield check (docs/v2/g2/data/g29/actor_yield/goals_park_in_lane.json): COCO
 * parks at (40.0, 12.0) on walker_dock's path (x = 40, y 8.75-14.75), north of the east-west forklift lane.
 * Through the gateway (coco.v1 nav_goal), then 40 s parked. Then the driver (tools/g2/actor_scenario.py,
 * started by the entrypoint) is sent SIGINT so it writes its summary, and its log is read.
 *
 * Pass: every actor moved (> 1.0 m along its poses), at least one HOLD while COCO stood in a lane (the
 * actors yield), no overlap step (COCO's circle never inside an actor's box), and the goal reached.
 * Evidence class: LIVE (a Gazebo simulation); the actors follow a SCENARIO RULE, not physics.
 */
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';

const [url, out, ...rest] = process.argv.slice(2);
const container = rest.includes('--container') ? rest[rest.indexOf('--container') + 1] : 'coco';
const GOAL = [40.0, 12.0];
const PARK_S = 40;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const dex = (...a) => execFileSync('docker', ['exec', container, ...a], { encoding: 'utf-8' });
const rec = { schema: 'coco_ros2.actors_round', version: 1, url, utc: new Date().toISOString(), goal: GOAL,
  park_s: PARK_S, errors: [] };

let last = null; let code = 1;
try {
  rec.driver_running_at_start = dex('sh', '-c', 'test -s /tmp/coco/actors.pid && kill -0 $(cat /tmp/coco/actors.pid) && echo yes || echo no').trim();
  const controlCode = dex('cat', '/tmp/coco/control_code').trim();
  const ws = new WebSocket(url);
  const acks = new Map(); let nextId = 1;
  const send = (f) => { const id = nextId++; ws.send(JSON.stringify({ ...f, id })); return id; };
  const answered = async (id, ms = 3000) => { const t0 = Date.now(); while (!acks.has(id) && Date.now() - t0 < ms) await sleep(50); return acks.get(id) ?? null; };
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = () => reject(new Error(`could not open ${url}`)); });
  ws.onmessage = (ev) => {
    if (typeof ev.data !== 'string') return;
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.type === 'telemetry') last = m; else if (m.type === 'ack' || m.type === 'error') acks.set(m.id, m);
  };
  send({ type: 'hello', client: 'coco-ros2 actors_round', binary: false });
  for (let i = 0; i < 100 && !last?.robot?.truth; i++) await sleep(100);
  rec.claim = (await answered(send({ type: 'claim', code: controlCode })))?.type ?? null;
  rec.set_mode = (await answered(send({ type: 'set_mode', mode: 'auto' })))?.type ?? null;
  await sleep(1000);
  const t0 = Date.now();
  rec.goal_ack = (await answered(send({ type: 'nav_goal', x: GOAL[0], y: GOAL[1] })))?.type ?? null;
  let status = null;
  for (let i = 0; i < 3000; i++) {                       // up to 300 s to cross the Depot
    await sleep(100);
    status = last?.nav?.goal?.status ?? null;
    if (Date.now() - t0 > 3000 && ['succeeded', 'aborted', 'canceled'].includes(status)) break;
  }
  rec.goal_status = status; rec.goal_seconds = (Date.now() - t0) / 1000;
  rec.truth_at_goal = last?.robot?.truth ?? null;
  await sleep(PARK_S * 1000);                           // parked on walker_dock's path
  rec.truth_after_park = last?.robot?.truth ?? null;
  await answered(send({ type: 'stop' }));
  ws.close();

  dex('sh', '-c', 'kill -INT $(cat /tmp/coco/actors.pid) 2>/dev/null; sleep 3; true');
  const lines = dex('cat', '/tmp/coco/actors.jsonl').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  let summary = null; try { summary = JSON.parse(dex('cat', '/tmp/coco/actor_scenario.json')); } catch { /* none */ }
  writeFileSync(out.replace(/\.json$/, '_actors.jsonl'), lines.map((l) => JSON.stringify(l)).join('\n') + '\n');
  // per-second pose lines (the start event also has an `actors` field: the list of ids)
  const steps = lines.filter((l) => l.actors && !Array.isArray(l.actors));
  const moved = {};
  for (let k = 1; k < steps.length; k++) {
    for (const [id, p] of Object.entries(steps[k].actors)) {
      const q = steps[k - 1].actors[id];
      if (q) moved[id] = (moved[id] ?? 0) + Math.hypot(p[0] - q[0], p[1] - q[1]);
    }
  }
  const holds = lines.filter((l) => l.event === 'hold');
  rec.actors = lines.find((l) => l.event === 'start')?.actors ?? Object.keys(steps[0]?.actors ?? {});
  rec.moved_m = Object.fromEntries(Object.entries(moved).map(([k, v]) => [k, Math.round(v * 100) / 100]));
  rec.hold_events = holds.length;
  rec.holds_by_actor = holds.reduce((a, h) => { const id = h.actor ?? h.id ?? '?'; a[id] = (a[id] ?? 0) + 1; return a; }, {});
  rec.first_hold = holds[0] ?? null;
  rec.summary = summary;
  const overlap = summary?.overlap_steps ?? null;
  rec.checks = {
    goal_reached: status === 'succeeded',
    every_actor_moved: rec.actors.length > 0 && rec.actors.every((id) => (moved[id] ?? 0) > 1.0),
    actors_yielded: holds.length > 0,
    no_overlap: overlap === 0,
  };
  rec.pass = Object.values(rec.checks).every(Boolean);
  code = rec.pass ? 0 : 1;
} catch (e) {
  rec.errors.push(String(e?.message ?? e));
  rec.pass = false;
}
writeFileSync(out, JSON.stringify(rec, null, 1) + '\n');
console.log(JSON.stringify({ pass: rec.pass, checks: rec.checks, moved_m: rec.moved_m, hold_events: rec.hold_events,
  holds_by_actor: rec.holds_by_actor, goal: rec.goal_status, errors: rec.errors }));
process.exit(code);
