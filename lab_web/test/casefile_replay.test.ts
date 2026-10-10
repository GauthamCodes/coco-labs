// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * A packed Case File in the viewer (M3.3): lab_web/casefiles/<id>.mcap,
 * committed (ADR 0005), parsed by src/arena/replay_case.ts into the replay
 * the Arena plays. Nothing is computed: every pose, scan and family the
 * replay holds is one in the file.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { create, fromBinary } from '@bufbuild/protobuf';
import { describe, expect, it } from 'vitest';

import { caseLens, isCaseFile } from '../src/arena/replay_case';
import { parseConverted } from '../src/arena/replay';
import { readRun } from '../src/schemas/mcap';
import { WorldGridSchema } from '../src/schemas/gen/coco/world/v1/world_pb';
import { TruthPoseBatchSchema } from '../src/schemas/gen/coco/truth/v1/truth_pb';
import { REPO } from './helpers';

const DIR = join(REPO, 'lab_web', 'casefiles');
const index = JSON.parse(readFileSync(join(DIR, 'index.json'), 'utf-8')) as { casefiles: { id: string; bytes: number; sha256: string }[] };
const bytes = (id: string) => new Uint8Array(readFileSync(join(DIR, `${id}.mcap`)));
// a stand-in map: the viewer is handed the map; parsing does not depend on what is in it
const grid = create(WorldGridSchema, { mapId: 'test', width: 4, height: 4, resolution: 1, originX: 0, originY: 0,
  occupancy: new Uint8Array(16), blocked: new Uint8Array(16) });

describe('a Case File in the viewer', () => {
  it('is recognised by its manifest, and is STACK', async () => {
    const run = await readRun(bytes('lab5_crossing_dwb_1'));
    expect(isCaseFile(run.manifest)).toBe(true);
    const rec = await parseConverted(bytes('lab5_crossing_dwb_1'), grid);
    expect(rec.evidence).toBe('STACK');
  });

  it('draws the robot where the stack believed it was, truth beside it, every 0.1 s', async () => {
    const run = await readRun(bytes('lab5_crossing_dwb_1'));
    const truth = run.messages.filter((m) => m.channel === 'coco.truth.pose.v1').flatMap((m) => {
      const b = fromBinary(TruthPoseBatchSchema, m.data);
      return [...b.tWorld].map((t, i) => [t, b.x[i]] as const);
    });
    const rec = await parseConverted(bytes('lab5_crossing_dwb_1'), grid);
    const dts = rec.ticks.slice(1).map((t, i) => t.t_world - rec.ticks[i].t_world);
    expect(Math.max(...dts) - Math.min(...dts)).toBeLessThan(1e-9);
    // each tick's truth is a recorded truth sample (the latest at or before it), never interpolated
    const xs = new Set(truth.map(([, x]) => x));
    expect(rec.ticks.every((t) => xs.has(t.truth![0]))).toBe(true);
  });

  it('carries the recorded scans, the controller\'s families and the global path', async () => {
    const rec = await parseConverted(bytes('lab5_crossing_dwb_1'), grid);
    expect(rec.world.lidar.samples).toBeGreaterThan(0);
    expect(rec.ranges.size).toBeGreaterThan(0);
    const channels = new Set([...rec.families!.values()].flat().map((f) => f.channel));
    expect(channels.has('coco.control.local.candidates.v1')).toBe(true);
    expect(channels.has('coco.control.local.command.v1')).toBe(true);
    expect(channels.has('coco.estimate.pose.v1')).toBe(true);
    expect(rec.ticks.some((t) => t.path && t.path.length >= 4)).toBe(true);
    expect(caseLens(rec)).toBe('move');
  });

  it('opens a Lab 4 search on the Decide lens with the mission\'s recorded transitions', async () => {
    const rec = await parseConverted(bytes('lab4_a1_fixed_red'), grid);
    const states = [...rec.families!.values()].flat().filter((f) => f.channel === 'coco.mission.fsm.transition.v1')
      .map((f) => (f.columns!.to_state as string[])[0]);
    expect(states.slice(0, 3)).toEqual(['IDLE', 'LOCALIZE', 'SELECT_SEARCH_REGION']);
    expect(states).toContain('COMPLETE');
    expect(caseLens(rec)).toBe('decide');
  });

  it('refuses to draw a Case File without its map', async () => {
    await expect(parseConverted(bytes('lab1_run_astar'))).rejects.toThrow(/map/);
  });

  it('every committed Case File is the one its index names', async () => {
    const { createHash } = await import('node:crypto');
    for (const e of index.casefiles) {
      const b = bytes(e.id);
      expect(b.byteLength).toBe(e.bytes);
      expect(createHash('sha256').update(b).digest('hex')).toBe(e.sha256);
    }
  });
});
