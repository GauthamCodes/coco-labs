// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** Play's levels (M3.5): generated/play/levels.json, from lab_web/play/levels.json. */

const BASE = import.meta.env.BASE_URL;

export interface Level { id: string; title: string; story?: string; [k: string]: unknown }
export interface Levels {
  schema: string; order: string[];
  challenges: Record<string, { title: string; goal: string; levels: Level[] }>;
}

let levelsP: Promise<Levels> | null = null;
export function loadLevels(): Promise<Levels> {
  levelsP ??= fetch(`${BASE}generated/play/levels.json`, { credentials: 'omit' }).then((r) => {
    if (!r.ok) throw new Error(`levels: HTTP ${r.status}`);
    return r.json() as Promise<Levels>;
  });
  return levelsP;
}

/** The Arena URL a challenge played in the Arena opens (map, detective). */
export function arenaPlayHref(challenge: string, lv: Level): string {
  const q = new URLSearchParams({ view: 'arena' });
  if (challenge === 'map-the-arena') {
    q.set('lens', 'map'); q.set('level', 'explain');
    for (const c of lv.config as string[]) q.append('cfg', c);
  } else {
    q.set('casefile', String(lv.casefile)); q.set('lens', 'localise'); q.set('level', 'explain');
  }
  q.set('play', challenge); q.set('pl', lv.id);
  return `?${q.toString()}`;
}
