// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Predict-then-reveal: one question before a run, and the measured answer
 * after it. The answer is read from the trace summaries coco_lab wrote;
 * nothing here searches.
 */

import type { TraceSummary } from '../bundle/model';

export type CostChange = 'more' | 'less' | 'same' | 'found' | 'lost' | 'none';

/** How the path cost moved from `before` to `after`. */
export function costChange(before: TraceSummary, after: TraceSummary): CostChange {
  const a = before.path_cost;
  const b = after.path_cost;
  if (a === null && b === null) return 'none';
  if (a === null) return 'found';
  if (b === null) return 'lost';
  const tol = 1e-9 * Math.max(1, Math.abs(a), Math.abs(b));
  if (Math.abs(b - a) <= tol) return 'same';
  return b > a ? 'more' : 'less';
}

export const COST_QUESTION = {
  question: 'Before you run it: will the new path cost more, less, or the same?',
  options: [['more', 'More'], ['same', 'The same'], ['less', 'Less']] as Array<[string, string]>,
};

/** The algorithms with the fewest expansions (more than one on a tie). */
export function fewestExpanded(rows: Array<{ algorithm: string; expansions: number }>): { min: number; algorithms: string[] } {
  const min = Math.min(...rows.map((r) => r.expansions));
  return { min, algorithms: rows.filter((r) => r.expansions === min).map((r) => r.algorithm) };
}

export interface Reveal {
  question: string;
  predicted: string | null; // null: the learner skipped the question
  measured: string;
  right: boolean | null; // null when skipped
}

export function revealCost(predicted: string | null, before: TraceSummary, after: TraceSummary,
  fmt: (x: number) => string): Reveal {
  const ch = costChange(before, after);
  const was = before.path_cost === null ? 'no path' : fmt(before.path_cost);
  const now = after.path_cost === null ? 'no path' : fmt(after.path_cost);
  const words: Record<CostChange, string> = {
    more: 'more', less: 'less', same: 'the same', found: 'a path now exists', lost: 'no path any more', none: 'still no path',
  };
  return {
    question: COST_QUESTION.question,
    predicted,
    measured: `${words[ch]}: the path cost went from ${was} to ${now}.`,
    right: predicted === null ? null : predicted === ch,
  };
}

export function revealFewest(predicted: string | null, rows: Array<{ algorithm: string; expansions: number }>,
  name: (a: string) => string): Reveal {
  const f = fewestExpanded(rows);
  const who = f.algorithms.map(name).join(' and ');
  return {
    question: 'Which will expand the fewest cells?',
    predicted: predicted === null ? null : name(predicted),
    measured: `${who} expanded the fewest: ${f.min} cell${f.min === 1 ? '' : 's'}${f.algorithms.length > 1 ? ' each (a tie)' : ''}.`,
    right: predicted === null ? null : f.algorithms.includes(predicted),
  };
}
