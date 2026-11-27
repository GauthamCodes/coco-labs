// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R5.5: the world editor's model (src/editor/model.ts) and its link (src/editor/level_link.ts): grid
 * snapping, axis-aligned walls, doors on walls, rotation (a rack's aisle turns with it), deletion (a
 * wall's doors go with it), undo/redo, and the World Spec v3 it writes (the Python reader validates it:
 * coco_lab/test/test_level_check.py builds the same kind of level).
 */
import { describe, expect, it } from 'vitest';
import { History, addDoor, asLevel, addGoal, addSolid, addWall, levelId, move, newLevel, remove, rotate, setStart, toSpec, turnStart } from '../src/editor/model';
import { decodeLevel, encodeLevel } from '../src/editor/level_link';

const depot = { robot: { radius: 0.22 }, arena: { resolution: 0.1 } };

describe('the world editor', () => {
  it('snaps to the grid and keeps walls along x or y', () => {
    let l = addWall(newLevel(), [1.2, 1.1], [6.9, 2.2])!;
    expect(l.pieces[0]).toEqual({ id: 'wall_1', kind: 'wall', from: [1, 1], to: [7, 1] });
    l = addWall(l, [3, 8], [3.2, 2])!;
    expect(l.pieces[1]).toMatchObject({ from: [3, 2], to: [3, 8] });              // ordered from -> to
    expect(addWall(l, [2, 2], [2.1, 2.2])).toBeNull();                             // no length: nothing
  });

  it('puts a door on the nearest wall, never near its ends', () => {
    let l = addWall(newLevel(), [0, 4], [10, 4])!;
    l = addDoor(l, [5.2, 4.3])!;
    expect(l.pieces[1]).toEqual({ id: 'door_2', kind: 'door', wall: 'wall_1', at: 5, width: 1.2 });
    expect(addDoor(l, [0.2, 4])).toBeNull();                                       // too near the end
    expect(addDoor(l, [5, 6])).toBeNull();                                         // no wall within 0.5 m
    expect(remove(l, 'wall_1').pieces).toEqual([]);                                // its door goes with it
  });

  it('rotates a rack and its aisle, moves pieces, turns the start', () => {
    let l = addSolid(newLevel(), 'rack', [4, 4]);
    l = rotate(l, 'rack_1');
    expect(l.pieces[0]).toMatchObject({ size: [1.1, 3.0], aisles: ['-x'] });
    l = move(l, 'rack_1', 1.3, -0.6);
    expect(l.pieces[0]).toMatchObject({ center: [5.5, 3.5] });
    l = turnStart(setStart(l, [2.2, 2.7]));
    expect(l.start).toEqual({ x: 2, y: 2.5, theta: Math.round((Math.PI / 2) * 1000) / 1000 });
  });

  it('undoes and redoes whole edits', () => {
    const h = new History(newLevel());
    h.push(addSolid(h.now, 'box', [3, 3]));
    h.push(addGoal(h.now, [8, 6]));
    expect([h.now.pieces.length, h.now.goals.length]).toEqual([1, 1]);
    expect(h.undo()).toBe(true); expect(h.now.goals).toEqual([]);
    expect(h.undo()).toBe(true); expect(h.now.pieces).toEqual([]);
    expect(h.undo()).toBe(false);
    expect(h.redo()).toBe(true); expect(h.now.pieces.length).toBe(1);
    h.push(addGoal(h.now, [1, 1]));
    expect(h.redo()).toBe(false);                                                  // a new edit drops the redo branch
  });

  it('writes a World Spec v3: outer walls on the bounds, then the pieces', () => {
    let l = addWall({ ...newLevel(), title: 'Two Rooms!' }, [6, 0], [6, 9])!;
    l = addSolid(addDoor(l, [6, 4.5])!, 'rack', [3, 6]);
    const s = toSpec(l, depot) as { id: string; spec_version: string; bounds: unknown; kit: { id: string; kind: string }[]; robot: unknown };
    expect(s.spec_version).toBe('coco.world_spec.v3');
    expect(s.id).toBe('editor_two_rooms');
    expect(levelId(l)).toBe('editor_two_rooms');
    expect(s.bounds).toEqual({ x_min: 0, x_max: 12, y_min: 0, y_max: 9 });
    expect(s.kit.map((k) => k.id)).toEqual(['outer_s', 'outer_n', 'outer_w', 'outer_e', 'wall_1', 'door_2', 'rack_3']);
    expect(s.kit[6]).toMatchObject({ kind: 'rack', aisle: 1.2, aisles: ['+y'], shelves: [0.3, 1.0, 1.7] });
    expect(s.robot).toBe(depot.robot);
  });

  it('round-trips a level through its link, and refuses a broken one', async () => {
    const l = addGoal(addSolid(newLevel(), 'bench', [5, 5]), [9, 7]);
    const token = await encodeLevel({ spec: toSpec(l, depot), goals: l.goals, editor: l });
    expect(token).toMatch(/^v1\.[A-Za-z0-9_-]+$/);
    const back = await decodeLevel(token);
    expect(back.goals).toEqual([[9, 7]]);
    expect(back.editor).toEqual(l);
    await expect(decodeLevel('v9.abc')).rejects.toThrow(/v1/);
    await expect(decodeLevel(`v1.${token.slice(3, 20)}`)).rejects.toThrow();
  });

  it('refuses hostile links: a deflate bomb stops at the cap, a broken editor state is ignored', async () => {
    // 8 MB of spaces deflate to a few kB: inflating stops at 512 kB, never 8 MB
    const big = new TextEncoder().encode(`{"spec":{"spec_version":"coco.world_spec.v3"},"goals":[]${' '.repeat(8 * 1024 * 1024)}}`);
    const z = new Uint8Array(await new Response(new Blob([big]).stream().pipeThrough(new CompressionStream('deflate-raw'))).arrayBuffer());
    let b = ''; for (const c of z) b += String.fromCharCode(c);
    const token = `v1.${btoa(b).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')}`;
    expect(token.length).toBeLessThan(64 * 1024);
    await expect(decodeLevel(token)).rejects.toThrow(/too large/);
    await expect(decodeLevel(`v1.${'A'.repeat(200 * 1024)}`)).rejects.toThrow(/too large/);
    const ok = addGoal(addSolid(newLevel(), 'rack', [5, 5]), [9, 7]);
    expect(asLevel(JSON.parse(JSON.stringify(ok)))).toEqual(ok);
    for (const bad of [null, 'x', { ...ok, pieces: 'x' }, { ...ok, w: 1e9 }, { ...ok, title: '<img src=x onerror=alert(1)>'.repeat(10) },
      { ...ok, pieces: [{ id: '<b>', kind: 'box', center: [1, 1], size: [1, 1], height: 1 }] },
      { ...ok, pieces: [{ id: 'box_1', kind: 'script', center: [1, 1] }] }, { ...ok, goals: [[1, Infinity]] }, { ...ok, start: { x: 1 } }]) {
      expect(asLevel(bad)).toBeNull();
    }
  });
});

import { pyReason } from '../src/arena/py_error';

describe('a worker error in words (R5.6)', () => {
  it('keeps a traceback\'s last line, and anything else as it is', () => {
    const tb = 'Traceback (most recent call last):\n  File "/home/pyodide/arena_glue.py", line 86, in init\n    _arena = Arena(...)\ncoco_lab.worldspec.WorldSpecError: robot: required';
    expect(pyReason(tb)).toBe('WorldSpecError: robot: required');
    expect(pyReason('the worker stopped')).toBe('the worker stopped');
  });
});
