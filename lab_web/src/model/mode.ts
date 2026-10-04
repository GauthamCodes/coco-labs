// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Mode labels (CLAUDE.md "COCO Lab" rule 4) and the rule-6 input check.
 *
 * The label comes from the bundle's own `provenance`, never from where the
 * UI found it (owner decision, PHASE_1D_PLAN.md):
 * - `recorded-run` -> "Replay — recorded real run"
 * - `glass-box` written by the Pyodide worker (`tool` lab_web/pyodide)
 *   -> "Replay — computed in your browser by coco_lab"
 * - any other `glass-box` -> "Replay — coco_lab computation (glass-box)"
 * - `sketch` (Lab 2, Localise): coco_lab's 2D browser model -- "Sketch —
 *   a model, not the robot", plus "computed in your browser" when the
 *   Pyodide worker wrote it. Its measured fidelity is shown beside it.
 * A browser recomputation is never presented as a robot run.
 */

import type { DecodedBundle, Provenance } from '../bundle/model';

export const PYODIDE_TOOL = 'lab_web/pyodide';

export interface ModeLabel {
  mode: 'Replay' | 'Sketch';
  text: string;
  kind: 'recorded' | 'browser' | 'glass-box' | 'sketch';
}

export function modeLabel(p: Pick<Provenance, 'source_kind' | 'tool'>): ModeLabel {
  switch (p.source_kind) {
    case 'recorded-run':
      return { mode: 'Replay', kind: 'recorded', text: 'Replay — recorded real run' };
    case 'glass-box':
      return p.tool === PYODIDE_TOOL
        ? { mode: 'Replay', kind: 'browser', text: 'Replay — computed in your browser by coco_lab' }
        : { mode: 'Replay', kind: 'glass-box', text: 'Replay — coco_lab computation (glass-box)' };
    case 'sketch':
      return p.tool === PYODIDE_TOOL
        ? { mode: 'Sketch', kind: 'sketch', text: 'Sketch — computed in your browser by coco_lab; a model, not the robot' }
        : { mode: 'Sketch', kind: 'sketch', text: 'Sketch — coco_lab\'s 2D model, not the robot' };
  }
}

/**
 * Rule 6: two runs are comparable only on identical inputs -- map, start,
 * goal, move model and seed. (1E's race mode uses this; 1D tests it.)
 */
export function sameInputs(a: DecodedBundle, b: DecodedBundle): boolean {
  const same = (x: unknown, y: unknown) => JSON.stringify(canon(x)) === JSON.stringify(canon(y));
  return a.map.contentHash === b.map.contentHash &&
    same(a.run.start, b.run.start) && same(a.run.goal, b.run.goal) &&
    same(a.run.graph.kind, b.run.graph.kind) && same(a.run.model, b.run.model) &&
    a.provenance.seed === b.provenance.seed;
}

function canon(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(canon);
  if (v && typeof v === 'object') {
    return Object.fromEntries(Object.keys(v).sort().map((k) => [k, canon((v as Record<string, unknown>)[k])]));
  }
  return v;
}
