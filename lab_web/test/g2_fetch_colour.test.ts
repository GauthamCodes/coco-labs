// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
// Fetch by colour (owner request 2026-10-24): the route, the bests, the chips' text, and the HUD's
// wording of the model's order -- and that they agree with coco_lab's rounds file.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { colourBestKey, colourFromQuery, colourHref, FETCH_COLOUR_RULES } from '../src/game/fetch_colour';
import { bestKey } from '../src/game/GameApp';
import { colourChip, colourObjective, FETCH_COLOURS, isFetch, primaryAction } from '../src/game/rules_view';
import { SPEC_FILES } from '../src/arena/protocol';
import { SPEC_FOR, type GameTick } from '../src/game/session';
import { REPO } from './helpers';

const DOC = JSON.parse(readFileSync(join(REPO, 'coco_lab', 'coco_lab', 'levels', 'coco_depot_colours_v1.fetch_colour.json'), 'utf-8')) as
  { rules: number; colours: string[]; level: string; rounds: Record<string, { diameter: number; object: string }> };

describe('Fetch by colour', () => {
  it('offers the rounds file\'s colours, rules and level, with their real diameters', () => {
    expect(FETCH_COLOURS.map((c) => c.id)).toEqual(DOC.colours);
    expect(FETCH_COLOUR_RULES).toBe(DOC.rules);
    expect(SPEC_FOR.depot_colours).toBe(`${DOC.level}.json`);
    expect(SPEC_FILES.depot).toBe('coco_depot_v1.json');
    for (const c of FETCH_COLOURS) expect(c.mm / 1000).toBeCloseTo(DOC.rounds[c.id].diameter, 9);
  });
  it('parses the colour from the link, or asks', () => {
    const q = (s: string) => new URLSearchParams(s);
    expect(colourFromQuery(q('view=play&game=fetch_colour&colour=blue'))).toBe('blue');
    expect(colourFromQuery(q('view=play&game=fetch_colour&colour=purple'))).toBeNull();
    expect(colourFromQuery(q('view=play&game=fetch_colour'))).toBeNull();
    expect(colourHref('/', 'green')).toBe('/?view=play&game=fetch_colour&colour=green');
    expect(colourHref('/', 'green', 'dijkstra')).toBe('/?view=play&game=fetch_colour&colour=green&planner=dijkstra');
  });
  it('keeps bests per colour and per planner, apart from Fetch Rush\'s', () => {
    expect(colourBestKey('red')).toBe('coco.play.best.v1.g2-fetch-colour.r1-red');
    expect(colourBestKey('red', 'astar')).toBe(colourBestKey('red'));
    expect(colourBestKey('yellow', 'greedy')).toBe('coco.play.best.v1.g2-fetch-colour.r1-yellow.planner-greedy');
    expect(bestKey(1, 'phone')).toBe('coco.play.best.v1.g1-fetch-rush.r4-phone.seed-1');
  });
  it('labels every chip with text, never colour alone', () => {
    expect(FETCH_COLOURS.map((c) => colourChip(c.id))).toEqual(['RED · 20 mm', 'GREEN · 24 mm', 'BLUE · 28 mm', 'YELLOW · 32 mm']);
    expect(colourObjective('red', false)).toBe('FETCH THE RED ROD → DISPATCH');
    expect(colourObjective('red', true)).toBe('CARRY THE RED ROD → DISPATCH');
  });
  it('GRAB takes only the chosen rod, DROP only at Dispatch', () => {
    expect(isFetch('fetch_colour') && isFetch('fetch_rush') && !isFetch('free')).toBe(true);
    const tick = { pose: [22, 7.6, 0], game: { assist: { phase: 'idle', carried: null }, fetch: { order: ['rod_blue', 'dispatch_drop'] } } } as unknown as GameTick;
    const cand = (id: string, rank: number) => ({ object_id: id, item: '', reason: '', rank, seen_by: 'camera', dist: 0.5, approach_x: null, approach_y: null });
    const zones = [{ id: 'dispatch_drop', role: 'drop', label: 'Dispatch', center: [23, 1.4] as [number, number], size: [3, 2] as [number, number] }];
    const base = { game: 'fetch_colour' as const, tick, zones, goal: null, auto: false, latched: false };
    expect(primaryAction({ ...base, cands: [cand('rod_green', 0)] })).toMatchObject({ enabled: false, why: 'Not that colour' });
    expect(primaryAction({ ...base, cands: [cand('rod_green', 0), cand('rod_blue', 1)] })).toMatchObject({ kind: 'grab', enabled: true, target: 'rod_blue' });
    const carrying = { ...tick, game: { ...tick.game, assist: { phase: 'carry', carried: 'rod_blue' } } } as unknown as GameTick;
    expect(primaryAction({ ...base, tick: carrying, cands: [] })).toMatchObject({ kind: 'drop', enabled: false, why: 'Go to DISPATCH' });
  });
});
