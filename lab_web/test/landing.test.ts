// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'vitest';

import { DEFAULT_LANDING } from '../site.config';
import { MISSION_FOR_VIEW, needsRunIds, route } from '../src/landing';

// Lab 1's bundles, which the site serves converted (generated/v2/index.json, M1.9)
const RUNS = new Set(['astar_open', 'bfs_no_path', 'lab1c_astar', 'arena_0_10m']);
const ARENA_LINKS = ['?view=arena', '?view=arena&perf', '?view=arena&run=abc', '?view=arena&replay=lab1c_astar'];

describe('routing (M2.10: v1 lab views retired, every v1 URL keeps working)', () => {
  it('ships the Arena as the default landing page', () => {
    expect(DEFAULT_LANDING).toBe('arena');
    expect(__LANDING__).toBe(process.env.LANDING ?? 'arena');
  });

  it('opens the three apps by name', () => {
    for (const q of ARENA_LINKS) expect(route(q, 'arena'), q).toEqual({ app: 'arena' });
    expect(route('?view=learn&mission=find-a-path&beat=2', 'v1')).toEqual({ app: 'learn' });
    expect(route('?view=live', 'arena')).toEqual({ app: 'live' });
    expect(route('?view=live&live=ws://127.0.0.1:8080/ws', 'arena')).toEqual({ app: 'live' });
    // a hand-trimmed Arena link (no view=arena) is still the Arena's
    expect(route('?run=abc', 'arena')).toEqual({ app: 'arena' });
    expect(route('?replay=lab1c_astar', 'arena')).toEqual({ app: 'arena' });
  });

  it('sends each bare v1 lab link to the mission that carries its claims', () => {
    expect(MISSION_FOR_VIEW).toEqual({ plan: 'find-a-path', localise: 'where-it-is', map: 'build-a-map', search: 'where-to-look', move: 'avoid-things' });
    for (const [view, mission] of Object.entries(MISSION_FOR_VIEW)) {
      expect(route(`?view=${view}`, 'arena')).toEqual({ redirect: `?view=learn&mission=${mission}` });
      expect(route(`?view=${view}&perf`, 'arena')).toEqual({ redirect: `?view=learn&mission=${mission}` });
    }
  });

  it('forwards a deep link into a v1 lab to the archive, query intact', () => {
    for (const q of ['?view=localise&loc=exhibits', '?view=map&scene=map_loop', '?view=move&move=replan', '?view=search&search=matrix',
      '?view=map&map=real', '?view=exhibit', '?view=nonsense', '?view=toString', '?view=constructor']) {
      expect(route(q, 'arena'), q).toEqual({ redirect: `v1/${q}` });
    }
  });

  it('opens an unchanged Lab 1 bundle as its converted run', () => {
    for (const q of ['?bundle=astar_open', '?bundle=astar_open&v=1', '?v=1&bundle=astar_open&h=0123456789ab', '?view=plan&bundle=astar_open&v=1',
      '?view=exhibit&bundle=astar_open']) {
      expect(route(q, 'arena', RUNS), q).toEqual({ redirect: '?view=arena&replay=astar_open' });
    }
  });

  it('forwards a Lab 1 link it cannot open unchanged to the archive, query intact', () => {
    for (const q of ['?v=1&bundle=astar_open&s=1.2.8.0.0', '?v=1&bundle=astar_open&e=AQI', '?bundle=not_a_bundle', '?v=1',
      '?v=2&bundle=astar_open', '?bundle=astar_open&x=1', '?view=localise&bundle=astar_open', '?bundle=Astar_Open']) {
      expect(route(q, 'arena', RUNS), q).toEqual({ redirect: `v1/${q}` });
    }
    // the run index did not load: never guess
    expect(route('?bundle=astar_open', 'arena', null)).toEqual({ redirect: 'v1/?bundle=astar_open' });
  });

  it('asks for the run index only for a Lab 1 link', () => {
    expect(needsRunIds('?bundle=astar_open')).toBe(true);
    expect(needsRunIds('?v=1')).toBe(true);
    for (const q of ['', '?view=plan', '?view=arena&replay=x', '?view=learn', '?view=live']) expect(needsRunIds(q), q).toBe(false);
  });

  it('the bare URL follows the build switch: the Arena, or the v1 archive', () => {
    expect(route('', 'arena')).toEqual({ app: 'arena' });
    expect(route('?perf', 'arena')).toEqual({ app: 'arena' });
    expect(route('', 'v1')).toEqual({ redirect: 'v1/' });
  });
});
