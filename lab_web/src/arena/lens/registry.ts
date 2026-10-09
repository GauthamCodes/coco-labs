// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The lens registry (M2.2; README 5.2 "Lenses"): one lens per family of
 * computation -- Plan, Localise, Map, Move, Decide. A lens lays out and
 * aggregates what coco_lab emitted; it never computes the algorithm. Each
 * declares:
 *
 * - the channel families it reads;
 * - its layers, each with a ROLE (computation, uncertainty, truth, world)
 *   and a palette colour; the role decides how it may be drawn (uncertainty
 *   is always translucent, truth always an outline: VISUAL_SYSTEM.md);
 * - which layers each disclosure level shows: Watch shows AT MOST TWO
 *   computation layers, Explain adds hover values and captions at key
 *   events, Inspect shows everything plus the inspector, the event log and
 *   charts (test/lens_registry.test.ts holds every lens to these rules);
 * - the metrics its Inspect charts plot (coco.metrics.values.v1 names);
 * - the Python pack its computation lives in (lazy-loaded on first use).
 */

import type { Palette } from '../render/palette';

export type LensId = 'plan' | 'localise' | 'map' | 'move' | 'decide';
export type Level = 'watch' | 'explain' | 'inspect';
export type Role = 'computation' | 'uncertainty' | 'truth' | 'world';

export const LEVELS: readonly Level[] = ['watch', 'explain', 'inspect'];
export const LEVEL_TITLES: Record<Level, string> = { watch: 'Watch', explain: 'Explain', inspect: 'Inspect' };

export interface LayerDef {
  id: string;
  label: string;
  role: Role;
  /** The palette key of its colour (the only place colours live). */
  colour: keyof Palette;
  /** The lowest level at which it is on by default. */
  from: Level;
  /** What it shows, for the legend and the Explain-level tooltip. */
  meaning: string;
}

export interface Lens {
  id: LensId;
  title: string;
  /** The robot's question this lens answers (README 7: missions are organised by them). */
  question: string;
  families: string[];
  layers: LayerDef[];
  /** coco.metrics.values.v1 metric names its Inspect charts plot. */
  charts: string[];
  /** The Python pack (lab_web/tools/arena_packs.json) its model code is in. */
  pack: string;
  /** The lowest milestone checkpoint its live computation arrives in. */
  since: string;
}

export const LENSES: readonly Lens[] = [
  {
    id: 'plan', title: 'Plan', question: 'How does a robot find a path?', pack: 'core', since: 'M1',
    families: ['plan.search', 'plan.incremental', 'plan.path'],
    charts: ['expansions', 'path_cost'],
    layers: [
      { id: 'frontier', label: 'frontier', role: 'computation', colour: 'frontier', from: 'watch', meaning: 'cells pushed but not yet expanded: the edge of the search' },
      { id: 'path', label: 'path', role: 'computation', colour: 'path', from: 'watch', meaning: 'the route the planner chose' },
      { id: 'closed', label: 'closed set', role: 'computation', colour: 'closed', from: 'explain', meaning: 'cells the search expanded' },
      { id: 'heatmap', label: 'heatmap', role: 'computation', colour: 'closed', from: 'inspect', meaning: 'the ORDER cells were expanded, dark first, bright last' },
    ],
  },
  {
    id: 'localise', title: 'Localise', question: 'How does a robot know where it is?', pack: 'localise', since: 'M2.3',
    families: ['estimate', 'localise.particles', 'localise.ekf'],
    charts: ['err_xy.mcl', 'err_xy.ekf', 'err_xy.odometry', 'n_eff'],
    layers: [
      { id: 'particles', label: 'particles', role: 'uncertainty', colour: 'particles', from: 'watch', meaning: 'MCL hypotheses of the pose; size = weight' },
      { id: 'estimate', label: 'estimate', role: 'computation', colour: 'estimate', from: 'watch', meaning: 'the pose the filter believes' },
      { id: 'covariance', label: 'covariance', role: 'uncertainty', colour: 'covariance', from: 'explain', meaning: "the estimate's 95 % ellipse" },
      { id: 'odometry', label: 'odometry', role: 'computation', colour: 'odometry', from: 'inspect', meaning: 'dead reckoning alone: wheel odometry, never corrected' },
    ],
  },
  {
    id: 'map', title: 'Map', question: 'How does it build a map?', pack: 'map', since: 'M2.4',
    families: ['map.grid', 'map.slam', 'estimate'],
    charts: ['ate', 'f1'],
    layers: [
      { id: 'built_map', label: 'built map', role: 'computation', colour: 'mapOccupied', from: 'watch', meaning: 'the occupancy the robot has built (log-odds); unknown is clear' },
      { id: 'slam_pose', label: 'SLAM pose', role: 'computation', colour: 'estimate', from: 'watch', meaning: "the SLAM's trajectory estimate" },
      { id: 'landmarks', label: 'landmarks', role: 'uncertainty', colour: 'landmark', from: 'explain', meaning: "EKF-SLAM's landmark means and ellipses (IDEALISED sensor)" },
      { id: 'slam_particles', label: 'SLAM particles', role: 'uncertainty', colour: 'particles', from: 'explain', meaning: "FastSLAM's trajectory hypotheses" },
      { id: 'graph', label: 'pose graph', role: 'computation', colour: 'graphNode', from: 'inspect', meaning: 'nodes and edges; loop closures in their own colour' },
    ],
  },
  {
    id: 'move', title: 'Move', question: 'How does it avoid things while following a path?', pack: 'move', since: 'M2.5',
    families: ['control.local'],
    charts: ['n_valid', 'cmd_v', 'tracking_error'],
    layers: [
      { id: 'chosen', label: 'chosen', role: 'computation', colour: 'chosen', from: 'watch', meaning: 'the trajectory the controller chose this cycle' },
      { id: 'candidates', label: 'candidates', role: 'computation', colour: 'candidate', from: 'watch', meaning: 'every candidate it scored (valid ones; cost shades them)' },
      { id: 'rejected', label: 'rejected', role: 'computation', colour: 'rejected', from: 'explain', meaning: 'candidates it refused, and why' },
      { id: 'local_window', label: 'local window', role: 'computation', colour: 'localWindow', from: 'explain', meaning: 'the part of the world the controller considers' },
      { id: 'lookahead', label: 'lookahead', role: 'computation', colour: 'lookahead', from: 'inspect', meaning: 'the path point a tracker steers for' },
      { id: 'given_path', label: 'given path', role: 'computation', colour: 'path', from: 'explain', meaning: 'the global path the controller was handed whole: a Lab 5 scenario’s frozen SmacPlanner2D path' },
      { id: 'actors', label: 'actors', role: 'world', colour: 'actor', from: 'watch', meaning: 'moving people, drawn at their collision radius (the Arena’s actors have collision bodies; Lab 5’s Gazebo actors had none)' },
    ],
  },
  {
    id: 'decide', title: 'Decide', question: 'How does it decide where to look?', pack: 'decide', since: 'M2.6',
    families: ['decide.search', 'sensor.detect', 'mission.fsm', 'arm'],
    charts: ['expected_cost', 'p_max'],
    layers: [
      { id: 'belief', label: 'belief', role: 'computation', colour: 'belief', from: 'watch', meaning: 'P(target in bay): the fill is the probability' },
      { id: 'detection', label: 'detections', role: 'computation', colour: 'detection', from: 'watch', meaning: 'what each look reported (detection probability labelled)' },
      { id: 'bays', label: 'bays', role: 'world', colour: 'bay', from: 'explain', meaning: "the four bays where a target may stand" },
    ],
  },
];

export const LENS_BY_ID = Object.fromEntries(LENSES.map((l) => [l.id, l])) as Record<LensId, Lens>;

const RANK: Record<Level, number> = { watch: 0, explain: 1, inspect: 2 };

/** The layers a lens shows by default at a level. */
export function defaultLayers(lens: Lens, level: Level): string[] {
  return lens.layers.filter((l) => RANK[l.from] <= RANK[level]).map((l) => l.id);
}

/** The Python pack a `config` input needs (its key's first part names the subsystem). */
export function packForConfig(choice: string): string {
  const head = choice.split('=')[0].split('.')[0];
  return ({ localise: 'localise', map: 'map', move: 'move', mission: 'decide', decide: 'decide' } as Record<string, string>)[head] ?? 'core';
}

/** Every layer id any lens owns, with its lens. */
export function layerOwner(id: string): Lens | null {
  return LENSES.find((l) => l.layers.some((x) => x.id === id)) ?? null;
}
