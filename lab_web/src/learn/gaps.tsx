// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * "Model gap" chips (M2.9): wherever a lesson depends on a measured gap
 * between the model and the Stack, a chip names it and opens to what was
 * measured, linking to docs/v2/FIDELITY_v1.md. The text is the site's
 * generated/fidelity.json, rendered at build from the committed
 * measurement (lab_web/tools/fidelity.py) -- never typed here.
 */

import { useEffect, useState } from 'react';

import { REPO_BLOB_URL } from '../../site.config';

export interface Gap { title: string; text: string; anchor: string }
export type Gaps = Record<string, Gap>;

let cached: Promise<Gaps> | null = null;

/** The chips' text, fetched once per page. */
export function loadGaps(base: string): Promise<Gaps> {
  cached ??= fetch(`${base}generated/fidelity.json`, { credentials: 'omit' })
    .then((r) => (r.ok ? r.json() : { gaps: {} })).then((j) => j.gaps as Gaps).catch(() => ({}));
  return cached;
}

export function useGaps(base: string): Gaps {
  const [g, setG] = useState<Gaps>({});
  useEffect(() => { void loadGaps(base).then(setG); }, [base]);
  return g;
}

/** The chips for `ids`, in order; an id the data lacks is not drawn. */
export function GapChips({ ids, gaps }: { ids: readonly string[]; gaps: Gaps }) {
  const shown = ids.filter((id) => gaps[id]);
  if (!shown.length) return null;
  return (
    <div className="gap-chips" data-testid="gap-chips">
      {shown.map((id) => (
        <details key={id} className="gap-chip" data-testid={`gap-${id}`}>
          <summary>Model gap: {gaps[id].title}</summary>
          <p>{gaps[id].text}{' '}
            <a href={`${REPO_BLOB_URL}docs/v2/FIDELITY_v1.md#${gaps[id].anchor}`} target="_blank" rel="noreferrer">Fidelity report</a></p>
        </details>
      ))}
    </div>
  );
}
