// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** The Arena's controls (M4.5): README §5.5's defaults, remapping, and storage through the preferences module. */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { actionFor, ACTIONS, DEFAULT_BINDINGS, loadBindings, rebind, resetBindings } from '../src/arena/controls';

/** A minimal localStorage on window, or one that throws (blocked storage). */
function fakeStorage(throws = false) {
  const m = new Map<string, string>();
  const s = {
    getItem: (k: string) => { if (throws) throw new Error('blocked'); return m.get(k) ?? null; },
    setItem: (k: string, v: string) => { if (throws) throw new Error('blocked'); m.set(k, v); },
    removeItem: (k: string) => { if (throws) throw new Error('blocked'); m.delete(k); },
  };
  (globalThis as unknown as { window: unknown }).window = { localStorage: s };
  return m;
}

describe('controls', () => {
  let saved: unknown;
  beforeEach(() => { saved = (globalThis as unknown as { window?: unknown }).window; });
  afterEach(() => { (globalThis as unknown as { window?: unknown }).window = saved; });

  it("the defaults are README §5.5's table", () => {
    const b = DEFAULT_BINDINGS;
    const want: [string, string][] = [['KeyW', 'forward'], ['KeyS', 'reverse'], ['KeyA', 'left'], ['KeyD', 'right'],
      ['ShiftLeft', 'precision'], ['Space', 'stop'], ['KeyR', 'release'], ['KeyE', 'context'], ['Tab', 'autonomy'],
      ['KeyC', 'camera_next'], ['KeyV', 'camera_follow'], ['Digit1', 'lens_1'], ['Digit5', 'lens_5'], ['KeyP', 'pause'],
      ['BracketLeft', 'step_back'], ['BracketRight', 'step_forward'], ['KeyH', 'help']];
    for (const [code, action] of want) expect(actionFor(code, b)).toBe(action);
    // every action has a key, and no key does two things
    const all = ACTIONS.flatMap((a) => b[a.id]);
    expect(ACTIONS.every((a) => b[a.id].length > 0)).toBe(true);
    expect(new Set(all).size).toBe(all.length);
  });

  it('a remap takes the key off its old action, is stored, and survives a reload', () => {
    const m = fakeStorage();
    const b = rebind(loadBindings(), 'stop', 'KeyX');
    expect(actionFor('KeyX', b)).toBe('stop');
    expect(actionFor('Space', b)).toBe('stop');                // the old key stays second
    const c = rebind(b, 'context', 'KeyX');                     // X moves to grasp
    expect(actionFor('KeyX', c)).toBe('context');
    expect(c.stop).toEqual(['Space']);
    expect([...m.keys()]).toEqual(['coco.prefs.v1.keys']);
    expect(loadBindings()).toEqual(c);                          // read back as stored
    expect(resetBindings()).toEqual(DEFAULT_BINDINGS);
    expect(m.size).toBe(0);
  });

  it('blocked storage changes nothing: the defaults, and remaps last for the page', () => {
    fakeStorage(true);
    expect(loadBindings()).toEqual(DEFAULT_BINDINGS);
    const b = rebind(loadBindings(), 'help', 'F1');
    expect(actionFor('F1', b)).toBe('help');
  });

  it('a stored value that is not bindings is ignored', () => {
    const m = fakeStorage();
    m.set('coco.prefs.v1.keys', JSON.stringify({ stop: 'Space' }));
    expect(loadBindings()).toEqual(DEFAULT_BINDINGS);
    m.set('coco.prefs.v1.keys', JSON.stringify({ nonsense: ['KeyQ'] }));
    expect(loadBindings()).toEqual(DEFAULT_BINDINGS);
  });
});
