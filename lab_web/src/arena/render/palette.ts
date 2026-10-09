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
}

export const PALETTES: Record<Theme, Palette> = {
  light: {
    background: '#f7f7f5', free: '#fbfbfa', occupied: '#3a3a40', unknown: '#c9c9cc',
    frontier: '#e66100', closed: '#4b6fc4', closedAlpha: 0.42, path: '#c4125a',
    lidar: '#0f8b8d', lidarAlpha: 0.55, robot: '#2b2b33', heading: '#ffd23f',
    footprint: '#6b6b75', truth: '#1a9641', goal: '#c4125a', pick: '#111111', text: '#1c1c22',
  },
  dark: {
    background: '#141418', free: '#1d1d22', occupied: '#b9b9c2', unknown: '#3a3a42',
    frontier: '#ff9a3c', closed: '#6f8ff0', closedAlpha: 0.45, path: '#ff5c9a',
    lidar: '#36c5c7', lidarAlpha: 0.5, robot: '#e8e8ee', heading: '#ffd23f',
    footprint: '#9a9aa6', truth: '#4fd27a', goal: '#ff5c9a', pick: '#ffffff', text: '#ececf1',
  },
};

/** The viridis ramp at 0..1 (5 stops, linear between them, in sRGB). */
export const VIRIDIS = ['#440154', '#3b528b', '#21918c', '#5ec962', '#fde725'];

export function currentTheme(): Theme {
  const q = new URLSearchParams(window.location.search).get('theme');
  if (q === 'light' || q === 'dark') return q;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
