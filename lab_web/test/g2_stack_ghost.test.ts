// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.6: Race Nav2's ghost (src/game/stack_ghost.ts) replays a recording -- the pose at round time
 * t is the recording's, interpolated between its 10 Hz samples and held at both ends -- and is
 * offered only for a round whose recording succeeded; the page's rules version is coco_lab's.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ghostFor, ghostForColour, ghostPoseAt, type GhostIndex, type StackGhost } from '../src/game/stack_ghost';
import { FETCH_RUSH_RULES } from '../src/game/rules_view';
import { REPO } from './helpers';

const track: StackGhost['track'] = [[0, 0, 0, 0], [0.1, 0.03, 0, 0], [0.2, 0.06, 0.01, 3.1], [0.3, 0.09, 0.02, -3.1]];

describe('the STACK ghost', () => {
  it('is the recording at t, interpolated, held at both ends', () => {
    expect(ghostPoseAt(track, -5)).toEqual([0, 0, 0]);
    expect(ghostPoseAt(track, 0.05)[0]).toBeCloseTo(0.015, 9);
    expect(ghostPoseAt(track, 99)).toEqual([0.09, 0.02, -3.1]);
    const th = ghostPoseAt(track, 0.25)[2];   // across the ±pi seam: the short way round
    expect(Math.abs(Math.atan2(Math.sin(th - Math.PI), Math.cos(th - Math.PI)))).toBeLessThan(0.1);
  });

  it('is offered only for a round whose recording succeeded', () => {
    const idx: GhostIndex = { schema: 's', version: 1, evidence: 'STACK', ghosts: [
      { file: 'a.json', rules: 4, mode: 'phone', seed: 1, bytes: 1, sha256: 'x', driving_s: 1, all_succeeded: true },
      { file: 'b.json', rules: 4, mode: 'phone', seed: 2, bytes: 1, sha256: 'x', driving_s: 1, all_succeeded: false }] };
    expect(ghostFor(idx, 4, 'phone', 1)?.file).toBe('a.json');
    expect(ghostFor(idx, 4, 'phone', 2)).toBeNull();
    expect(ghostFor(idx, 3, 'phone', 1)).toBeNull();
    expect(ghostFor(null, 4, 'phone', 1)).toBeNull();
  });

  it('takes the first listed recording of a round (the index puts the same rules\' recording first)', () => {
    const idx: GhostIndex = { schema: 's', version: 1, evidence: 'STACK', ghosts: [
      { file: 'r5.json', rules: 5, mode: 'phone', seed: 1, recorded_rules: 5, bytes: 1, sha256: 'x', driving_s: 1, all_succeeded: true },
      { file: 'r4.json', rules: 5, mode: 'phone', seed: 1, recorded_rules: 4, bytes: 1, sha256: 'x', driving_s: 1, all_succeeded: true }] };
    expect(ghostFor(idx, 5, 'phone', 1)?.file).toBe('r5.json');
  });

  it('G2: a Fetch by colour recording is found by colour, never as a Fetch Rush round', () => {
    const idx: GhostIndex = { schema: 's', version: 1, evidence: 'STACK', ghosts: [
      { file: 'c_red.json', rules: 2, game: 'fetch_colour', colour: 'red', bytes: 1, sha256: 'x', driving_s: 1, all_succeeded: true },
      { file: 'c_blue.json', rules: 2, game: 'fetch_colour', colour: 'blue', bytes: 1, sha256: 'x', driving_s: 1, all_succeeded: false }] };
    expect(ghostForColour(idx, 2, 'red')?.file).toBe('c_red.json');
    expect(ghostForColour(idx, 2, 'blue')).toBeNull();
    expect(ghostForColour(idx, 1, 'red')).toBeNull();
    expect(ghostFor(idx, 2, 'phone', 1)).toBeNull();
  });

  it('the page plays the rules coco_lab plays', () => {
    const py = readFileSync(join(REPO, 'coco_lab', 'coco_lab', 'games.py'), 'utf-8');
    expect(Number(/^FETCH_RUSH_RULES = (\d+)$/m.exec(py)![1])).toBe(FETCH_RUSH_RULES);
  });
});
