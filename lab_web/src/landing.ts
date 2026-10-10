// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Where a URL goes (M2.10: the v1 lab views are retired, every v1 URL keeps
 * working). Pure, so every URL form is tested (test/landing.test.ts).
 *
 * - `?view=arena`, `?view=learn` open those apps; `?view=live` opens the
 *   Live view, which stays in `main` until M5.
 * - A BARE v1 lab link (`?view=plan|localise|map|search|move`, nothing else
 *   but `perf`) goes to the Learn mission that carries that lab's claims.
 * - A Lab 1 bundle or share link (`?bundle=`, `?v=1`) naming a bundle
 *   unchanged -- no settings `s`, no map edits `e` -- opens its converted
 *   run in the Arena (`?view=arena&replay=<id>`; the trace is the bundle's,
 *   converted losslessly at M1.9).
 * - Everything else a v1 page understood -- a share link with settings or
 *   edits, a deep link into a lab (`loc=`, `scene=`, `map=`, `move=`,
 *   `search=`), `?view=exhibit`, an unknown bundle or view -- is forwarded
 *   to the frozen v1 build at `v1/` with its query intact
 *   (docs/v2/adr/0003-v1-archive.md).
 * - The bare URL opens the Arena, or the v1 archive when the build says
 *   `LANDING=v1` (site.config.ts).
 */

/** What the bare URL opens (the build-time switch). */
export type Landing = 'arena' | 'v1';
/** The code-split apps this build serves. */
export type AppId = 'arena' | 'learn' | 'live' | 'casefiles' | 'play';
/** Open an app here, or go to a URL relative to the site root. */
export type Route = { app: AppId } | { redirect: string };

/** The Learn mission that carries each retired v1 lab's claims (docs/v2/M2_CLAIMS_COVERAGE.md). */
export const MISSION_FOR_VIEW: Readonly<Record<string, string>> = {
  plan: 'find-a-path', localise: 'where-it-is', map: 'build-a-map', search: 'where-to-look', move: 'avoid-things',
};
/** Parameters that never changed what a v1 page showed. */
const PASSIVE = new Set(['perf']);
/** What a Lab 1 link may carry and still name its bundle unchanged. */
const PLAIN_LAB1 = new Set(['bundle', 'v', 'h', 'view', 'perf']);

/** The v1 archive with the query intact. */
export const toV1 = (search: string): Route => ({ redirect: `v1/${search}` });

/**
 * Route a query string. `runIds` is the converted runs this site serves
 * (generated/v2/index.json); it is only consulted for a Lab 1 link, and
 * null (not loaded) forwards such a link to v1 rather than guessing.
 */
export function route(search: string, landing: Landing, runIds: ReadonlySet<string> | null = null): Route {
  const q = new URLSearchParams(search);
  const view = q.get('view');
  if (view === 'arena') return { app: 'arena' };
  if (view === 'learn') return { app: 'learn' };
  if (view === 'live') return { app: 'live' };
  if (view === 'casefiles') return { app: 'casefiles' }; // M3.3
  if (view === 'play') return { app: 'play' }; // M3.5
  if (q.has('bundle') || q.has('v')) {
    const id = q.get('bundle') ?? '';
    const plain = [...q.keys()].every((k) => PLAIN_LAB1.has(k)) && (q.get('v') ?? '1') === '1'
      && (view === null || view === 'plan' || view === 'exhibit');
    return plain && runIds?.has(id) && /^[a-z0-9_]{1,64}$/.test(id)
      ? { redirect: `?view=arena&replay=${id}` } : toV1(search);
  }
  if (view !== null) {
    const extra = [...q.keys()].filter((k) => k !== 'view' && !PASSIVE.has(k));
    const mission = Object.hasOwn(MISSION_FOR_VIEW, view) ? MISSION_FOR_VIEW[view] : undefined;
    return mission && extra.length === 0 ? { redirect: `?view=learn&mission=${mission}` } : toV1(search);
  }
  // Arena-only parameters (its links always add view=arena; a hand-trimmed one still works)
  if (q.has('run') || q.has('replay')) return { app: 'arena' };
  return landing === 'v1' ? toV1('') : { app: 'arena' };
}

/** Whether routing `search` needs the converted-run index first. */
export const needsRunIds = (search: string): boolean => {
  const q = new URLSearchParams(search);
  return !['arena', 'learn', 'live', 'casefiles', 'play'].includes(q.get('view') ?? '') && (q.has('bundle') || q.has('v'));
};
