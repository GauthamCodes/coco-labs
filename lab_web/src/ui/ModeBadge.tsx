// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import type { Provenance } from '../bundle/model';
import { modeLabel } from '../model/mode';

/** Always visible (rule 4). Its text comes from the bundle's provenance. */
export function ModeBadge({ provenance }: { provenance: Provenance | null }) {
  if (!provenance) {
    return <span className="mode-badge mode-none" data-testid="mode-badge">Replay — no bundle loaded</span>;
  }
  const m = modeLabel(provenance);
  return <span className={`mode-badge mode-${m.kind}`} data-testid="mode-badge">{m.text}</span>;
}
