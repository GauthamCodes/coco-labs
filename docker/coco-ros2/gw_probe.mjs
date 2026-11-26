// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/*
 * R5.2: the LIVE control gateway from outside the container, as the website uses it.
 *
 *   node docker/coco-ros2/gw_probe.mjs ws://127.0.0.1:8766/ws OUT.json [--container coco]
 *
 * The gateway is COCO's own platform_server (coco_web, remote:=true, coco.v1; Gautham's decision
 * 2026-11-26: the bridge is read-only, control goes through a gateway restricted by construction).
 * In order: hello -> welcome (coco.v1, the commands); telemetry arrives; set_mode teleop; drive
 * 0.15 m/s for 3 s and COCO's Gazebo truth moves; STOP -> latched and the wheels stop; set_mode
 * auto; nav_goal 1 m ahead -> NavigateToPose reports a status; STOP. While driving, ROS itself is
 * asked (in the container: `coco-ros2 check`) who publishes the wheels (only cmd_vel_arbiter) and
 * the arbiter's teleop input (only the gateway). Then the origin allowlist: a foreign Origin is
 * refused at the handshake (403), the Pages site's is accepted (101).
 *
 * Everything is written to OUT.json. Exit 0 only if every check passes.
 * Evidence class: LIVE (COCO's ROS 2 stack running now: a Gazebo simulation, never hardware).
 */
import { execFile, execFileSync } from 'node:child_process';
import { promisify } from 'node:util';
import { writeFileSync } from 'node:fs';
import http from 'node:http';

const [url, out, ...rest] = process.argv.slice(2);
if (!url || !out) { console.error('usage: gw_probe.mjs WS_URL OUT.json [--container NAME]'); process.exit(2); }
const container = rest.includes('--container') ? rest[rest.indexOf('--container') + 1] : null;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rec = {
  schema: 'coco_ros2.gw_probe', version: 1, url, utc: new Date().toISOString(),
  evidence_class: "LIVE (COCO's ROS 2 stack running now: a Gazebo simulation, never hardware)",
  welcome: null, acks: [], errors_from_server: [], telemetry_frames: 0, steps: {}, errors: [],
};
let last = null;           // the latest telemetry
const acks = new Map();    // id -> ack/error frame

// Asynchronous on purpose: a blocking exec froze this probe's event loop for seconds, so it sent no
// drive frames and answered no keep-alive, and the gateway ended the session (CI run 45874896939).
const execFileP = promisify(execFile);
async function inContainer() {
  if (!container) return null;
  try {
    const { stdout: t } = await execFileP('docker', ['exec', container, 'coco-ros2', 'check', '--json', '--window', '3'],
      { encoding: 'utf-8', timeout: 90_000 });
    const r = JSON.parse(t);
    return { wheel_topic_publishers: r.required_also?.wheel_topic_publishers ?? null,
             teleop_publishers: r.recorded?.teleop_publishers ?? null };
  } catch (e) { return { error: String(e?.message ?? e).slice(0, 300) }; }
}

const truthXY = () => (last?.robot?.truth ? [last.robot.truth.x, last.robot.truth.y] : null);
const dist = (a, b) => (a && b ? Math.hypot(a[0] - b[0], a[1] - b[1]) : null);

function originStatus(origin) {
  const u = new URL(url.replace(/^ws/, 'http'));
  return new Promise((resolve) => {
    const req = http.request({ host: u.hostname, port: u.port, path: u.pathname, headers: {
      Connection: 'Upgrade', Upgrade: 'websocket', 'Sec-WebSocket-Version': '13',
      'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==', Origin: origin } });
    req.on('upgrade', (res, socket) => { socket.destroy(); resolve(res.statusCode); });
    req.on('response', (res) => { res.resume(); resolve(res.statusCode); });
    req.on('error', (e) => resolve(String(e.message)));
    req.setTimeout(5000, () => { req.destroy(); resolve('timeout'); });
    req.end();
  });
}

let code = 1;
let nextId = 1;
try {
  const ws = new WebSocket(url);
  const send = (frame) => { const id = nextId++; ws.send(JSON.stringify({ ...frame, id })); return id; };
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = () => reject(new Error(`could not open ${url}`)); });
  ws.onclose = (e) => { rec.closed = { at_ms: Date.now(), code: e.code, reason: e.reason }; };
  ws.onmessage = (ev) => {
    if (typeof ev.data !== 'string') return;              // binary frames (camera, map) are not needed here
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.type === 'welcome') rec.welcome = { protocol: m.protocol, commands: m.commands, limits: m.limits };
    else if (m.type === 'telemetry') { last = m; rec.telemetry_frames++; }
    else if (m.type === 'ack' || m.type === 'error') {
      acks.set(m.id, m);
      (m.type === 'ack' ? rec.acks : rec.errors_from_server).push({ id: m.id, command: m.command, code: m.code, message: m.message });
    }
  };
  const answered = async (id, ms = 3000) => { const t0 = Date.now(); while (!acks.has(id) && Date.now() - t0 < ms) await sleep(50); return acks.get(id) ?? null; };

  send({ type: 'hello', client: 'coco-ros2 gw_probe', binary: false });
  for (let i = 0; i < 100 && !(rec.welcome && last?.robot?.truth); i++) await sleep(100);
  // code access (remote mode): driving without the code is refused; the code is read from the container
  const refused = await answered(send({ type: 'drive', linear: 0.1, angular: 0 }));
  const controlCode = container ? execFileSync('docker', ['exec', container, 'cat', '/tmp/coco/control_code'],
    { encoding: 'utf-8' }).trim() : null;
  const claim = controlCode ? await answered(send({ type: 'claim', code: controlCode })) : null;
  rec.steps.code = { drive_without_code: refused?.type === 'error' ? refused.code : refused?.type ?? null,
    claim: claim?.type ?? null, code_length: controlCode?.length ?? null };
  rec.steps.welcome = { protocol: rec.welcome?.protocol ?? null,
    has_commands: ['drive', 'stop', 'set_mode', 'nav_goal'].every((c) => rec.welcome?.commands?.includes(c)),
    telemetry: rec.telemetry_frames > 0, truth: truthXY() };

  const teleop = await answered(send({ type: 'set_mode', mode: 'teleop' }));
  await sleep(800);
  const p0 = truthXY();
  const vmax = [];
  let during = null;
  const t0 = Date.now();
  while (Date.now() - t0 < 3000) {
    send({ type: 'drive', linear: 0.15, angular: 0 });
    vmax.push(Math.abs(last?.robot?.velocity?.linear ?? 0));
    if (!during && Date.now() - t0 > 1500) during = 'pending';
    await sleep(100);
    if (during === 'pending') {                            // keep driving while ROS is asked
      const keep = setInterval(() => ws.send(JSON.stringify({ type: 'drive', linear: 0.15, angular: 0 })), 100);
      during = await inContainer(); clearInterval(keep);
    }
  }
  const p1 = truthXY();
  rec.steps.drive = { set_mode_teleop: teleop?.type ?? null, arbiter_mode: last?.platform?.arbiter?.mode ?? null,
    moved_m: dist(p0, p1), max_reported_linear: Math.max(0, ...vmax), in_container: during };

  const stopAck = await answered(send({ type: 'stop' }));
  await sleep(1500);
  const p2 = truthXY(); await sleep(1000); const p3 = truthXY();
  rec.steps.stop = { ack: stopAck?.type ?? null, latched: last?.platform?.stop?.latched ?? null,
    arbiter_mode: last?.platform?.arbiter?.mode ?? null, moved_after_stop_m: dist(p2, p3),
    linear_after_stop: last?.robot?.velocity?.linear ?? null };

  const auto = await answered(send({ type: 'set_mode', mode: 'auto' }));
  await sleep(1000);
  const pose = last?.robot?.pose;
  const gx = pose ? pose.x + Math.cos(pose.yaw) : null, gy = pose ? pose.y + Math.sin(pose.yaw) : null;
  const goalAck = pose ? await answered(send({ type: 'nav_goal', x: gx, y: gy })) : null;
  let status = null, pathLen = 0;
  for (let i = 0; i < 200 && !status; i++) {
    await sleep(100);
    status = last?.nav?.goal?.status ?? null;
    pathLen = last?.nav?.path?.length ?? 0;
  }
  for (let i = 0; i < 50 && pathLen === 0; i++) { await sleep(100); pathLen = last?.nav?.path?.length ?? 0; }
  rec.steps.goal = { set_mode_auto: auto?.type ?? null, latched_after_auto: last?.platform?.stop?.latched ?? null,
    goal: pose ? [gx, gy] : null, ack: goalAck?.type ?? null, nav_status: status, path_points: pathLen };
  await answered(send({ type: 'stop' }));
  ws.close();
  await sleep(300);

  rec.steps.origins = { foreign: await originStatus('https://evil.example'),
                        pages: await originStatus('https://gauthamcodes.github.io') };

  const isArbiter = (n) => String(n).replace(/^\/+/, '') === 'cmd_vel_arbiter';
  const w = rec.steps.drive.in_container;
  rec.acceptance = {
    drive_without_code_refused: rec.steps.code.drive_without_code !== null && rec.steps.code.drive_without_code !== 'ack',
    claim_with_code: rec.steps.code.claim === 'ack',
    welcome_coco_v1: rec.steps.welcome.protocol === 'coco.v1' && rec.steps.welcome.has_commands && rec.steps.welcome.telemetry,
    drive_moves_coco: rec.steps.drive.set_mode_teleop === 'ack' && (rec.steps.drive.moved_m ?? 0) > 0.1,
    wheels_only_arbiter: Array.isArray(w?.wheel_topic_publishers) && w.wheel_topic_publishers.length === 1 && isArbiter(w.wheel_topic_publishers[0]),
    teleop_input_is_the_gateway: Array.isArray(w?.teleop_publishers) && w.teleop_publishers.length > 0
      && w.teleop_publishers.every((n) => String(n).replace(/^\/+/, '') === 'coco_web_platform'),
    stop_latches_and_holds: rec.steps.stop.ack === 'ack' && rec.steps.stop.latched === true && (rec.steps.stop.moved_after_stop_m ?? 1) < 0.02,
    goal_reaches_nav2: rec.steps.goal.ack === 'ack' && rec.steps.goal.nav_status !== null,
    foreign_origin_refused: rec.steps.origins.foreign === 403,
    pages_origin_accepted: rec.steps.origins.pages === 101,
  };
  rec.pass = Object.values(rec.acceptance).every(Boolean);
  code = rec.pass ? 0 : 1;
} catch (e) {
  rec.errors.push(String(e?.message ?? e));
  rec.pass = false;
}
writeFileSync(out, JSON.stringify(rec, null, 1) + '\n');
console.log(JSON.stringify({ pass: rec.pass, acceptance: rec.acceptance, steps: rec.steps, errors: rec.errors }, null, 1));
process.exit(code);
