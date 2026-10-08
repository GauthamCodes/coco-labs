// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Live tab: one decoder (coco_web's), one fixture set (coco_web's), no
 * topic names, intents only from the server's own vocabulary, and the
 * honest labels pinned.
 */

import { readdirSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { isZero, keysVelocity, stickVelocity } from '../src/live/drive';
import {
  autonomousLabel, controlHolder, DISCOVERS, fallbackWarning, idleLine, LANE_TOLD, liveLabel, localisationNote, overriding,
  searchLine, sourceWords,
} from '../src/live/labels';
import { fit, toCanvas, toMap } from '../src/live/mapdraw';
import { INTENT_TYPES, type Telemetry } from '../src/live/protocol';

const here = fileURLToPath(new URL('.', import.meta.url));
const repo = join(here, '..', '..');
const require = createRequire(import.meta.url);
// coco_web's decoder, the very file the build ships as dist/coco/frame.js.
const { decodeFrame } = require(join(repo, 'coco_web', 'web', 'frame.js')) as {
  decodeFrame(b: ArrayBuffer): { stream: string; header: { seq: number; dropped: number }; payload: ArrayBuffer; ranges?: (number | null)[] };
};
const fixtures = JSON.parse(readFileSync(join(repo, 'coco_web', 'test', 'fixtures', 'frames.json'), 'utf-8')) as {
  valid: Record<string, { blob: string; stream: string; seq: number; dropped: number; payload_bytes: number; ranges?: (number | null)[] }>;
  invalid: Record<string, string>;
};
const buf = (b64: string) => { const b = Buffer.from(b64, 'base64'); return b.buffer.slice(b.byteOffset, b.byteOffset + b.length); };

describe('binary frames: coco_web/web/frame.js over coco_web\'s committed fixtures', () => {
  it('decodes every valid frame to the encoder\'s values', () => {
    expect(Object.keys(fixtures.valid).sort()).toEqual(['camera', 'depth', 'lidar']);
    for (const [name, spec] of Object.entries(fixtures.valid)) {
      const f = decodeFrame(buf(spec.blob));
      expect(f.stream, name).toBe(spec.stream);
      expect(f.header.seq, name).toBe(spec.seq);
      expect(f.header.dropped, name).toBe(spec.dropped);
      expect(f.payload.byteLength, name).toBe(spec.payload_bytes);
      if (spec.ranges) expect(f.ranges?.map((r) => (r === null ? null : Number(r.toFixed(3))))).toEqual(spec.ranges);
    }
  });
  it('refuses every broken frame', () => {
    expect(Object.keys(fixtures.invalid).length).toBeGreaterThanOrEqual(15);
    for (const [name, b64] of Object.entries(fixtures.invalid)) {
      expect(() => decodeFrame(buf(b64)), name).toThrow();
    }
  });
});

describe('the browser never names a topic', () => {
  // Needles harvested from the server's own source, like coco_web's leak
  // test: every quoted ROS name platform_server.py and safety.py use.
  const needles = new Set<string>();
  for (const f of ['platform_server.py', 'safety.py']) {
    const src = readFileSync(join(repo, 'coco_web', 'coco_web', f), 'utf-8');
    for (const m of src.matchAll(/'(\/[a-z_]+(?:\/[a-z_]+)*)'/g)) needles.add(m[1]);
  }
  const liveFiles = [
    ...readdirSync(join(here, '..', 'src', 'live')).map((n) => join(here, '..', 'src', 'live', n)),
    join(here, '..', 'src', 'ui', 'LiveView.tsx'),
  ];
  it('harvested a real needle list', () => {
    for (const n of ['/cmd_vel_teleop', '/mission/mode', '/goal_pose', '/model/coco/odometry']) {
      expect(needles.has(n), n).toBe(true);
    }
  });
  it('no Live source file contains one', () => {
    for (const f of liveFiles) {
      const text = readFileSync(f, 'utf-8');
      for (const n of needles) expect(text.includes(`'${n}'`) || text.includes(`"${n}"`), `${f}: ${n}`).toBe(false);
    }
  });
  it('every intent the tab sends is in coco.v1\'s own vocabulary', () => {
    const proto = readFileSync(join(repo, 'coco_web', 'coco_web', 'protocol.py'), 'utf-8');
    const start = proto.indexOf('_CLIENT_SCHEMA = {');
    const schema = proto.slice(start, proto.indexOf('\n}', start));
    const server = new Set([...schema.matchAll(/'([a-z_]+)': (?:\{|set\()/g)].map((m) => m[1]));
    for (const t of INTENT_TYPES) expect(server.has(t), t).toBe(true);
  });
});

describe('driving', () => {
  const lim = { linear: 0.5, angular: 1.2 };
  it('stick up is forward, right turns right, saturating at the limits', () => {
    expect(stickVelocity(0, 1, lim)).toEqual({ linear: 0.5, angular: 0 });
    expect(stickVelocity(1, 0, lim)).toEqual({ linear: 0, angular: -1.2 });
    const far = stickVelocity(0, 5, lim);
    expect(far.linear).toBeCloseTo(0.5);
    expect(stickVelocity(Number.NaN, 0, lim)).toEqual({ linear: 0, angular: 0 });
  });
  it('keys ask for 60 % and opposite keys cancel', () => {
    expect(keysVelocity(new Set(['w']), lim)).toEqual({ linear: 0.3, angular: 0 });
    expect(isZero(keysVelocity(new Set(['w', 's', 'a', 'd']), lim))).toBe(true);
  });
});

describe('honest labels', () => {
  it('labels the mode, local or remote (rule 4)', () => {
    expect(liveLabel('ws://localhost:8080/ws')).toBe('Live Stack (simulated) — local');
    expect(liveLabel('ws://127.0.0.1:8080/ws')).toBe('Live Stack (simulated) — local');
    expect(liveLabel('wss://coco.example.net/ws')).toBe('Live Stack (simulated) — scheduled demo');
  });
  // Phase 5: the label comes from what the RUNNING mission reports
  // (/mission/search via coco_web), never from a constant.
  const search = (mode: 'discover' | 'told' | null, extra = {}) => ({
    online: true, mode, policy: 'expected_cost', regions: ['bay_1', 'bay_2', 'bay_3', 'bay_4'],
    order: [], current: null, searched: [], belief: [0.25, 0.25, 0.25, 0.25], discovered: null,
    surveys: 0, seen: [], driven: 0, detection: 0.9, ...extra,
  });
  it('says the robot discovers the target only when the mission says it searches', () => {
    expect(autonomousLabel(search('discover'))).toEqual({ kind: 'discover', text: DISCOVERS });
    expect(DISCOVERS).toContain('told only the colour');
  });
  it('says the mission is told the bay when it was launched told', () => {
    expect(autonomousLabel(search('told'))).toEqual({ kind: 'told', text: LANE_TOLD });
    expect(LANE_TOLD).toContain('resolve_lane()');
    expect(LANE_TOLD).toContain('lane_for_colour()');
  });
  it('claims neither when the mission has not reported (an older stack)', () => {
    for (const s of [null, undefined, { ...search('discover'), online: false }, search(null)]) {
      const l = autonomousLabel(s);
      expect(l.kind).toBe('unknown');
      expect(l.text).not.toContain('discovers');
    }
  });
  it('shows the search as it happens, from the mission\'s own line', () => {
    expect(searchLine(search('told'))).toBeNull();
    expect(searchLine(search('discover'))).toContain('belief bay_1 25%');
    const line = searchLine(search('discover', {
      searched: ['bay_3'], current: 'bay_4', seen: ['blue'], belief: [0.3226, 0.3226, 0.0323, 0.3226],
    }))!;
    expect(line).toContain('searched: bay_3');
    expect(line).toContain('now: bay_4');
    expect(line).toContain('last look saw blue');
    expect(searchLine(search('discover', { discovered: 'bay_4', current: 'bay_4' }))).toContain('found in bay_4');
  });
  it('warns only when the server fell back', () => {
    expect(fallbackWarning(null)).toBeNull();
    expect(fallbackWarning({ config: { source: 'coco_config', fallbacks: [] } } as never)).toBeNull();
    expect(fallbackWarning({ config: { source: 'fallback', fallbacks: ['colours'] } } as never)).toMatch(/FALLBACK.*colours/);
  });
  const t = (pilot: string | null, active: string | null, missionActive = false, localised = true) => ({
    platform: { pilot, arbiter: { active, mode: null, online: true }, health: 'HEALTHY' },
    mission: missionActive ? { active: true } : null,
    robot: { online: true, localised },
  }) as unknown as Telemetry;
  it('names who holds control and what drives the wheels', () => {
    expect(controlHolder(t('abc', 'teleop'), 'abc')).toBe('you');
    expect(controlHolder(t('xyz', 'teleop'), 'abc')).toBe('another browser');
    expect(controlHolder(t(null, 'nav'), 'abc')).toBe('the robot (autonomous)');
    expect(controlHolder(t(null, null), 'abc')).toBe('nobody');
    expect(sourceWords('rl')).toBe('the RL ramp policy');
    expect(sourceWords(null)).toMatch(/nothing/);
  });
  it('shows preemption only while a person overrides a running mission', () => {
    expect(overriding(t('abc', 'teleop', true))).toBe(true);
    expect(overriding(t('abc', 'teleop', false))).toBe(false);
    expect(overriding(t(null, 'nav', true))).toBe(false);
  });
  it('says "not localised yet" instead of pretending', () => {
    expect(localisationNote(t(null, null, false, false))).toMatch(/Not localised yet/);
    expect(localisationNote(t(null, null, false, true))).toBeNull();
  });
});

describe('map transform', () => {
  it('canvas <-> map round-trips, and map y is up', () => {
    const v = fit({ width: 200, height: 100, resolution: 0.05, origin: { x: -2, y: -1 } }, 400, 200);
    const [px, py] = toCanvas(v, 1.5, 0.5);
    const [x, y] = toMap(v, px, py);
    expect(x).toBeCloseTo(1.5);
    expect(y).toBeCloseTo(0.5);
    expect(toCanvas(v, 0, 1)[1]).toBeLessThan(toCanvas(v, 0, 0)[1]);
  });
});

describe('the idle line names who holds the lease', () => {
  it('shows a countdown only while the driver holds it', () => {
    expect(idleLine({ access: 'code', over: null, lease: 'driver', idle_left_s: 41.2 })).toBe(' Idle release in 42 s.');
  });
  it('says autonomy holds it, with no countdown, and that the cap still applies', () => {
    const line = idleLine({ access: 'code', over: null, lease: 'autonomy', idle_left_s: null });
    expect(line).toContain('paused: autonomy is running');
    expect(line).toContain('session cap still applies');
    expect(line).not.toMatch(/\d+ s/);
  });
  it('says nothing in open access or without a block', () => {
    expect(idleLine({ access: 'open', over: null })).toBe('');
    expect(idleLine(null)).toBe('');
  });
});
