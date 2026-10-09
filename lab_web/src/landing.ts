// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** Which of the two code-split apps a URL opens. */
export type Landing = 'arena' | 'v1';

/**
 * `?view=arena` always opens the Arena. Every v1 link names its view
 * (`?view=plan`, `?view=live`, ...) or is a v1 share link (`?bundle=`,
 * `?v=`), and always opens v1. Only the BARE URL depends on `landing`, the
 * build-time switch (`site.config.ts` `DEFAULT_LANDING`, or `LANDING=`).
 */
export function chooseApp(search: string, landing: Landing): Landing {
  const q = new URLSearchParams(search);
  if (q.get('view') === 'arena') return 'arena';
  if (q.has('view') || q.has('bundle') || q.has('v')) return 'v1';
  // Arena-only parameters (its links always add view=arena; a hand-trimmed one still works)
  if (q.has('run') || q.has('replay')) return 'arena';
  return landing;
}
