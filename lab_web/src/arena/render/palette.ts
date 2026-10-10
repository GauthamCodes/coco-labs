// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The visual design system v1 (docs/v2/VISUAL_SYSTEM.md): ONE fixed colour
 * per layer, in a light and a dark theme. A layer never borrows another's
 * colour; truth is always an outline, never a fill; uncertainty (M2) is
 * always translucent. The heatmap ramp is viridis (perceptually uniform,
 * readable in greyscale and by the common colour-vision deficiencies).
 */

export type Theme = 'light' | 'dark';

export interface Palette {
  background: string;
  free: string;
  occupied: string;
  unknown: string;
  frontier: string;     // pushed, not yet expanded: the edge of the search
  closed: string;       // expanded (closed set)
  closedAlpha: number;
  path: string;         // the chosen path
  lidar: string;        // beams
  lidarAlpha: number;
  robot: string;        // COCO's body (from the Gazebo chassis mesh)
  heading: string;
  footprint: string;    // the collision circle the planner inflates by
  truth: string;        // ground truth: outline only, dashed
  goal: string;
  pick: string;         // the inspected cell
  text: string;
  // -- M2.2: the whole loop's layers (docs/v2/VISUAL_SYSTEM.md, "M2 layers") --
  particles: string;    // MCL particles (uncertainty: translucent)
  particlesAlpha: number;
  estimate: string;     // an estimator's pose (belief): solid arrow
  covariance: string;   // a covariance ellipse (uncertainty: translucent fill)
  covarianceAlpha: number;
  odometry: string;     // dead reckoning's pose
  mapFree: string;      // the BUILT map: log-odds ramp from free ...
  mapOccupied: string;  // ... to occupied (unknown: a veil of `unknown`)
  landmark: string;     // EKF-SLAM landmark means (on the IDEALISED sensor)
  landmarkAlpha: number;
  graphNode: string;    // pose-graph nodes
  graphEdge: string;    // odometry / scan-match edges
  graphLoop: string;    // loop-closure edges
  candidate: string;    // a valid candidate trajectory (cost shades it)
  candidateAlpha: number;
  rejected: string;     // a rejected candidate
  rejectedAlpha: number;
  chosen: string;       // the trajectory the controller chose
  lookahead: string;    // the path point a tracker steers for
  localWindow: string;  // the controller's local window (dashed)
  belief: string;       // a region's belief (fill alpha = probability)
  beliefAlpha: number;
  detection: string;    // a detection report
  actor: string;        // a moving actor (with its collision body)
  bay: string;          // bay outlines
}

export const PALETTES: Record<Theme, Palette> = {
  light: {
    background: '#f7f7f5', free: '#fbfbfa', occupied: '#3a3a40', unknown: '#c9c9cc',
    frontier: '#e66100', closed: '#4b6fc4', closedAlpha: 0.42, path: '#c4125a',
    lidar: '#0f8b8d', lidarAlpha: 0.55, robot: '#2b2b33', heading: '#ffd23f',
    footprint: '#6b6b75', truth: '#1a9641', goal: '#c4125a', pick: '#111111', text: '#1c1c22',
    particles: '#7b3294', particlesAlpha: 0.35, estimate: '#5e3c99', covariance: '#b2abd2', covarianceAlpha: 0.3,
    odometry: '#8c510a', mapFree: '#f4f4f0', mapOccupied: '#252529', landmark: '#d01c8b', landmarkAlpha: 0.45, graphNode: '#01665e',
    graphEdge: '#80cdc1', graphLoop: '#c51b7d', candidate: '#2c7bb6', candidateAlpha: 0.35, rejected: '#d7191c',
    rejectedAlpha: 0.25, chosen: '#fdae61', lookahead: '#a6611a', localWindow: '#545454', belief: '#e08214',
    beliefAlpha: 0.55, detection: '#008837', actor: '#b35806', bay: '#6a6a74',
  },
  dark: {
    background: '#141418', free: '#1d1d22', occupied: '#b9b9c2', unknown: '#3a3a42',
    frontier: '#ff9a3c', closed: '#6f8ff0', closedAlpha: 0.45, path: '#ff5c9a',
    lidar: '#36c5c7', lidarAlpha: 0.5, robot: '#e8e8ee', heading: '#ffd23f',
    footprint: '#9a9aa6', truth: '#4fd27a', goal: '#ff5c9a', pick: '#ffffff', text: '#ececf1',
    particles: '#c2a5cf', particlesAlpha: 0.4, estimate: '#b8a6e6', covariance: '#8073ac', covarianceAlpha: 0.35,
    odometry: '#dfc27d', mapFree: '#26262c', mapOccupied: '#e0e0e8', landmark: '#f1b6da', landmarkAlpha: 0.5, graphNode: '#5ab4ac',
    graphEdge: '#2a7f78', graphLoop: '#f1b6da', candidate: '#64b0e6', candidateAlpha: 0.35, rejected: '#ff6b6b',
    rejectedAlpha: 0.25, chosen: '#fee090', lookahead: '#e6b36a', localWindow: '#9a9aa6', belief: '#fdb863',
    beliefAlpha: 0.5, detection: '#5aae61', actor: '#f1a340', bay: '#8a8a96',
  },
};

/** The viridis ramp at 0..1 (5 stops, linear between them, in sRGB). */
export const VIRIDIS = ['#440154', '#3b528b', '#21918c', '#5ec962', '#fde725'];

export function currentTheme(): Theme {
  const q = new URLSearchParams(window.location.search).get('theme');
  if (q === 'light' || q === 'dark') return q;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
