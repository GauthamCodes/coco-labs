// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { describe, it, expect } from 'vitest';
import { deflateSync } from 'three/addons/libs/fflate.module.js';
import { decodeChallenge, boundedId, LIMITS } from '../src/links/bounds.mjs';
import { decodeRun } from '../src/arena/share';
const H = 'a'.repeat(64);
const encode = (x: unknown, z = false) => Buffer.from(z ? deflateSync(new TextEncoder().encode(JSON.stringify(x))) : JSON.stringify(x)).toString('base64url');
const q = (i: unknown, z = false) => new URLSearchParams(`c=race-the-ghost&l=warm-up&${z ? 'z' : 's'}=${encode({v:1,h:H,r:H,i}, z)}`);
describe('shared link boundaries before simulation', () => {
  for (const zipped of [false, true]) {
    it.each([[
      { tick: LIMITS.first_tick + 1, kind: 'teleop' },
    ], [{ tick: 10 ** 12, kind: 'teleop' }]])(`rejects oversized first ticks (${zipped ? 'z' : 's'}) in 50 ms`, row => {
      const start = performance.now();
      expect(() => decodeChallenge(q([row], zipped))).toThrow(/tick/);
      expect(performance.now() - start).toBeLessThan(50);
    });
    it(`bounds input count (${zipped})`, () => expect(() => decodeChallenge(q(Array(LIMITS.inputs + 1).fill({ tick:0,kind:'stop' }), zipped))).toThrow(/inputs/));
    it(`bounds total ticks (${zipped})`, () => expect(() => decodeChallenge(q({ticks: LIMITS.ticks+1,log:[]}, zipped))).toThrow(/ticks/));
  }
  it.each(['c','l','s','z'])('bounds %s even when another payload is present', field => {
    const params = q([]);
    params.set(field, 'A'.repeat(LIMITS.encoded + 1));
    const start = performance.now();
    expect(() => decodeChallenge(params)).toThrow();
    expect(performance.now() - start).toBeLessThan(50);
  });
  it('bounds replay identifiers', () => expect(() => boundedId('a'.repeat(LIMITS.id+1),'replay',true)).toThrow(/replay/));
  it('refuses compression bombs before allocating their full output', () => {
    const params = new URLSearchParams(`c=race-the-ghost&l=warm-up&z=${encode({v:1,h:H,r:H,i:['x'.repeat(LIMITS.json*100)]},true)}`);
    const start = performance.now();
    expect(() => decodeChallenge(params)).toThrow(/JSON/);
    expect(performance.now()-start).toBeLessThan(50);
  });
  it.each(['ticks','inputs','encoded','first'])('bounds run %s', field => {
    const d = {v:1,s:H,c:H,e:1,t:10,i:[] as number[][]};
    if (field==='ticks') d.t=LIMITS.ticks+1;
    if (field==='inputs') d.i=Array(LIMITS.inputs+1).fill([0,2]);
    if (field==='first') d.i=[[LIMITS.first_tick+1,2]];
    const payload=field==='encoded'?'a'.repeat(LIMITS.encoded+1):encode(d);
    expect(() => decodeRun(payload)).toThrow();
  });
});
