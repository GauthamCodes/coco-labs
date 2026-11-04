// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.3: the Algorithm Studio's starter files: coco_lab/coco_lab/templates/*.py, the very files
 * the native parity check runs (tools/r2/parity.mjs), imported as text. Never modules here.
 */
import plannerAstar from '../../../coco_lab/coco_lab/templates/planner_astar.py?raw';
import plannerGreedy from '../../../coco_lab/coco_lab/templates/planner_greedy.py?raw';
import plannerEmpty from '../../../coco_lab/coco_lab/templates/planner_empty.py?raw';
import controllerPurePursuit from '../../../coco_lab/coco_lab/templates/controller_pure_pursuit.py?raw';
import controllerEmpty from '../../../coco_lab/coco_lab/templates/controller_empty.py?raw';
import localiserParticleFilter from '../../../coco_lab/coco_lab/templates/localiser_particle_filter.py?raw';
import localiserEmpty from '../../../coco_lab/coco_lab/templates/localiser_empty.py?raw';
import teachHeuristic from '../../../coco_lab/coco_lab/templates/teach_heuristic.py?raw';
import teachTuneDwa from '../../../coco_lab/coco_lab/templates/teach_tune_dwa.py?raw';

export type Kind = 'planner' | 'controller' | 'localiser';
export type StudioFamily = 'planning' | 'control' | 'localisation';
export const FAMILY_OF: Record<Kind, StudioFamily> = { planner: 'planning', controller: 'control', localiser: 'localisation' };

export interface Template { id: string; label: string; kind: Kind; source: string; blurb: string; teaching?: boolean }

export const TEMPLATES: Template[] = [
  { id: 'planner_astar', label: 'Planner: A*', kind: 'planner', source: plannerAstar, blurb: 'A* on Nav2’s costmap, well commented.' },
  { id: 'planner_greedy', label: 'Planner: greedy best-first', kind: 'planner', source: plannerGreedy, blurb: 'Fast, few expansions, not optimal.' },
  { id: 'planner_empty', label: 'Planner: empty', kind: 'planner', source: plannerEmpty, blurb: 'The contract and a straight line to replace.' },
  { id: 'controller_pure_pursuit', label: 'Controller: pure pursuit', kind: 'controller', source: controllerPurePursuit, blurb: 'Chase a point one lookahead along the path.' },
  { id: 'controller_empty', label: 'Controller: empty', kind: 'controller', source: controllerEmpty, blurb: 'The contract and a go-to-goal start.' },
  { id: 'localiser_particle_filter', label: 'Localiser: particle filter', kind: 'localiser', source: localiserParticleFilter, blurb: 'A minimal Monte Carlo localisation.' },
  { id: 'localiser_empty', label: 'Localiser: empty', kind: 'localiser', source: localiserEmpty, blurb: 'The contract and dead reckoning.' },
  { id: 'teach_heuristic', label: 'Try it yourself: write the heuristic', kind: 'planner', source: teachHeuristic, blurb: 'A* with its heuristic left to you.', teaching: true },
  { id: 'teach_tune_dwa', label: 'Try it yourself: tune DWA', kind: 'controller', source: teachTuneDwa, blurb: 'DWA with its critic weights exposed.', teaching: true },
];

export const templateById = (id: string): Template | undefined => TEMPLATES.find((t) => t.id === id);

/** Which contract a file implements (the worker's guard decides for real; this picks the family to offer). */
export function kindOf(source: string): Kind | null {
  const found = (['plan', 'control', 'localise'] as const).filter((f) => new RegExp(`^def ${f}\\s*\\(`, 'm').test(source));
  if (found.length !== 1) return null;
  return ({ plan: 'planner', control: 'controller', localise: 'localiser' } as const)[found[0]];
}

/** The sha256 of the file's UTF-8 bytes: what a spec, a link and the leaderboard name it by. */
export async function codeSha256(source: string): Promise<string> {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(source));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}
