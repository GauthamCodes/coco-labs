// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Explain level (M2.2): a short caption at each KEY event of a lens's
 * families, read off the batches the model emitted at the shown tick. A
 * caption names what happened in the model's own terms; it computes
 * nothing (the numbers are the batch's).
 */

import type { LensId } from './registry';
import type { FamilyBatch, FamilyStore } from './store';

const num = (b: FamilyBatch | null, k: string, i = 0): number | null => {
  const c = b?.columns[k] as ArrayLike<number> | undefined;
  return c && c.length > i ? Number(c[i]) : null;
};
const str = (b: FamilyBatch | null, k: string, i = 0): string | null => {
  const c = b?.columns[k] as string[] | undefined;
  return c && c.length > i ? c[i] : null;
};

/** The caption for `lens` at `tick`, or null when nothing key happened then. */
export function caption(lens: LensId, store: FamilyStore, tick: number): string | null {
  const at = (ch: string) => store.at(ch, tick).at(-1) ?? null;
  if (lens === 'localise') {
    const u = at('coco.localise.particles.update.v1');
    const inj = num(u, 'injected');
    if (inj && inj > 0) return `MCL injected ${inj} random particles: its measurements fit worse than they used to, so it hedges against being lost.`;
    const e = at('coco.localise.ekf.update.v1');
    const gated = num(e, 'beams_gated');
    if (gated && gated > 0) return `The EKF gated ${gated} beams: they disagreed with its prediction too much to trust.`;
    return null;
  }
  if (lens === 'map') {
    const n = at('coco.map.slam.nodes.v1');
    if (n && n.scalars.stage === 'optimised') return `Loop closure: the pose graph was optimised (chi² ${Number(n.scalars.chi2).toFixed(2)}).`;
    return null;
  }
  if (lens === 'move') {
    const c = at('coco.control.local.command.v1');
    const st = str(c, 'status');
    // a recorded Lab 5 cycle (M2.7): 'eval' carries Nav2's own counts, 'rollout*' only a drawing
    if (st === 'eval') {
      const nv = num(c, 'n_valid'); const nc = num(c, 'n_candidates');
      return nv === null || nv < 0 ? `Nav2 scored ${nc} candidates this cycle.` : `Nav2 scored ${nc} candidates this cycle; ${nv} were valid.`;
    }
    if (st?.startsWith('rollout')) return null;
    if (st && st !== 'ok') {
      const nv = num(c, 'n_valid'); const nc = num(c, 'n_candidates');
      return st === 'no_valid_candidate' ? `No valid candidate: all ${nc} trajectories were rejected (${nv} valid), so the controller stops.`
        : st === 'path_outside_window' ? 'The path is outside the local window: from where the robot believes it is, there is nothing to follow.'
          : `Controller: ${st.replace(/_/g, ' ')}.`;
    }
    return null;
  }
  if (lens === 'decide') {
    const t = at('coco.mission.fsm.transition.v1');
    const reason = str(t, 'reason');
    if (reason) return `Mission: ${str(t, 'from_state')} → ${str(t, 'to_state')}. ${reason}`;
    const o = at('coco.decide.search.observation.v1');
    if (o) {
      const found = (o.columns.found as boolean[])[0];
      return found ? 'Found: the target is in this bay.' : 'A miss: the belief in that bay drops by Bayes’ rule, and the others rise.';
    }
    const a = at('coco.decide.search.action.v1');
    if (a) return `Next bay chosen: ${str(a, 'reason')}`;
    return null;
  }
  return null;
}
