// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Links between a Learn mission (M2.8) and the Arena. Pure, so both apps
 * import it without pulling in the other's code.
 *
 * A beat opens the Arena with `lens`, `level`, `replay` (which it already
 * reads) and `cfg` lines, plus `mission` + `beat` for the way back. `cfg`
 * lines are whole-loop settings the Arena sends as config inputs; it
 * refuses a key it does not know, so the URL can only ask for what the
 * model already offers (lab_web/tools/test_missions.py applies every
 * mission's lines to the Python Arena).
 */

/** What a beat links to (a mission file's `arena:`). */
export interface ArenaLink {
  lens?: string;
  level?: string;
  replay?: string;
  cfg?: string[];
}

const CFG = /^[a-z_]+(\.[a-z_]+)+=[A-Za-z0-9_.,+-]{1,64}$/;
const MISSION = /^[a-z0-9-]{1,64}$/;
const MAX_CFG = 12;

/** The `cfg` lines of an Arena URL that have a config's form (at most 12). */
export function cfgFromParams(params: URLSearchParams): string[] {
  return params.getAll('cfg').filter((c) => CFG.test(c)).slice(0, MAX_CFG);
}

/** The Learn link back to the beat that opened this Arena, or null. */
export function missionBackLink(params: URLSearchParams): string | null {
  const m = params.get('mission');
  const b = Number(params.get('beat'));
  if (!m || !MISSION.test(m) || !Number.isInteger(b) || b < 0 || b > 6) return null;
  return `?view=learn&mission=${m}&beat=${b}`;
}

/** The Arena URL (relative to the site root) for a mission's beat. */
export function arenaHref(missionId: string, beat: number, link: ArenaLink): string {
  const q = new URLSearchParams({ view: 'arena' });
  if (link.replay) q.set('replay', link.replay);
  if (link.lens) q.set('lens', link.lens);
  if (link.level) q.set('level', link.level);
  for (const c of link.cfg ?? []) q.append('cfg', c);
  q.set('mission', missionId);
  q.set('beat', String(beat));
  return `?${q.toString()}`;
}
