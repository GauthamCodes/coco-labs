// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Night Shift: the single source for CSS variables and rendering/type tokens.
 * Computation roles retain their established hues; truth is always an outline.
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

const computation: Record<Theme, Palette> = {
  light: {
    background: '#f7f7f5', free: '#fbfbfa', occupied: '#3a3a40', unknown: '#c9c9cc',
    frontier: '#e66100', closed: '#4b6fc4', closedAlpha: 0.42, path: '#c4125a',
    lidar: '#0f8b8d', lidarAlpha: 0.55, robot: '#2b2b33', heading: '#ffd23f',
    footprint: '#6b6b75', truth: '#1a9641', goal: '#c4125a', pick: '#111111', text: '#1c1c22',
    particles: '#7b3294', particlesAlpha: 0.35, estimate: '#5e3c99', covariance: '#b2abd2', covarianceAlpha: 0.3,
    odometry: '#8c510a', mapFree: '#f4f4f0', mapOccupied: '#252529', landmark: '#d01c8b', landmarkAlpha: 0.45, graphNode: '#01665e',
    graphEdge: '#80cdc1', graphLoop: '#c51b7d', candidate: '#2c7bb6', candidateAlpha: 0.35, rejected: '#d7191c',
    rejectedAlpha: 0.25, chosen: '#a66200', lookahead: '#a6611a', localWindow: '#545454', belief: '#e08214',
    beliefAlpha: 0.55, detection: '#008837', actor: '#b35806', bay: '#6a6a74',
  },
  dark: {
    background: '#10151a', free: '#1a242c', occupied: '#9aa6ae', unknown: '#35434f',
    frontier: '#ff9a3c', closed: '#6f8ff0', closedAlpha: 0.45, path: '#ff5c9a',
    lidar: '#36c5c7', lidarAlpha: 0.5, robot: '#e8e8ee', heading: '#ffd23f',
    footprint: '#9a9aa6', truth: '#4fd27a', goal: '#ff5c9a', pick: '#ffffff', text: '#ececf1',
    particles: '#c2a5cf', particlesAlpha: 0.4, estimate: '#b8a6e6', covariance: '#8073ac', covarianceAlpha: 0.35,
    odometry: '#dfc27d', mapFree: '#26262c', mapOccupied: '#e0e0e8', landmark: '#f1b6da', landmarkAlpha: 0.5, graphNode: '#5ab4ac',
    graphEdge: '#2a7f78', graphLoop: '#f1b6da', candidate: '#64b0e6', candidateAlpha: 0.35, rejected: '#df6b54',
    rejectedAlpha: 0.25, chosen: '#fee090', lookahead: '#e6b36a', localWindow: '#9a9aa6', belief: '#fdb863',
    beliefAlpha: 0.5, detection: '#5aae61', actor: '#f1a340', bay: '#8a8a96',
  },
};


export const TOKENS = {
  computation,
  viridis: ['#440154', '#3b528b', '#21918c', '#5ec962', '#fde725'],
  warehouse: {
    dark: { sky: '#a2b4c2', ground: '#18242b', workLight: '#ffd5a3', ambient: .65, key: 2.2, floor: '#202d36', structure: '#45515b' },
    light: { sky: '#f2f4f7', ground: '#8a8478', workLight: '#fff1df', ambient: 1.2, key: 1.6, floor: '#b5bbb6', structure: '#8c9697' },
  },
  colours: {
    dark: { badgeModel:'#c4afff', badgeStack:'#a6c9e4', labelSuccess:'#92d9b9', labelWarning:'#eed6ae', labelError:'#ffb3bc', bg: '#10151a', fg: '#edf0f2', muted: '#acb6be', line: '#3e4e5c', panel: '#1b252e', panel2: '#26343f', accent: '#eed6ae', recorded: '#a6c9e4', browser: '#d5dbe0', glass: '#bac3c9', errorBg: '#451b24', errorFg: '#ffd3d9' },
    light: { badgeModel:'#5937b4', badgeStack:'#225774', labelSuccess:'#1d6449', labelWarning:'#754313', labelError:'#9a2533', bg: '#eceee9', fg: '#202a32', muted: '#505e66', line: '#a2b1b8', panel: '#fafbf7', panel2: '#e1e6df', accent: '#654316', recorded: '#225774', browser: '#36464f', glass: '#505e66', errorBg: '#f7e0df', errorFg: '#7a1b20' },
  },
  type: { ui: "'Manrope Variable', sans-serif", display: "'Outfit Variable', sans-serif", label: 14, body: 16, lead: 18, section: 26, displaySize: 76, phoneDisplay: 52, compactDisplay: 56 },
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, scene: 48, hero: 64 },
  radius: { sm: 6, md: 12, lg: 20, pill: 999 },
  elevation: { low: '0 6px 20px rgba(0,0,0,0.18)', high: '0 20px 64px rgba(0,0,0,0.32)' },
  motion: { fast: 150, normal: 200, slow: 250, camera: 400, ease: 'cubic-bezier(.2,.7,.2,1)' },
} as const;

const cssName = (name: string) => name.replace(/[A-Z]/g, (c) => '-' + c.toLowerCase());
/** Inlined by Vite before the app CSS, so the first paint is dark too. */
export const TOKEN_CSS = (() => {
  const common = [
    ['font-ui', TOKENS.type.ui], ['font-display', TOKENS.type.display],
    ...Object.entries(TOKENS.type).filter(([, value]) => typeof value === 'number').map(([key, value]) => ['type-' + cssName(key), value + 'px']),
    ...Object.entries(TOKENS.spacing).map(([key, value]) => ['space-' + key, value + 'px']),
    ...Object.entries(TOKENS.radius).map(([key, value]) => ['radius-' + key, value + 'px']),
    ...Object.entries(TOKENS.elevation).map(([key, value]) => ['elevation-' + key, value]),
    ...Object.entries(TOKENS.motion).map(([key, value]) => ['motion-' + key, typeof value === 'number' ? value + 'ms' : value]),
    ['touch', '48px'],
  ];
  const declarations = (pairs: readonly (readonly unknown[])[]) => pairs.map(([key, value]) => `--${key}:${value}`).join(';');
  return (['dark', 'light'] as const).map((theme) => {
    const selector = theme === 'dark' ? ':root:not([data-theme="light"])' : ':root[data-theme="light"]';
    const vars = [...common, ...Object.entries(TOKENS.colours[theme]).map(([key, value]) => [cssName(key), value]),
      ...Object.entries(computation[theme]).map(([key, value]) => ['compute-' + cssName(key), value])];
    return `${selector}{${declarations(vars)};color-scheme:${theme};font-family:var(--font-ui);font-size:var(--type-body)}`;
  }).join('\n') + `
body{font-family:var(--font-ui)}
h1,h2,h3{font-family:var(--font-display);font-weight:500;letter-spacing:-.025em}
button,input,select,textarea{font-family:inherit}
button,a,input,select{transition:background-color var(--motion-normal) var(--motion-ease),border-color var(--motion-normal) var(--motion-ease)}
:focus-visible{outline:3px solid var(--accent);outline-offset:4px}
:root[data-motion="reduced"] *,:root[data-motion="reduced"] *::before,:root[data-motion="reduced"] *::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important;scroll-behavior:auto!important}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important;scroll-behavior:auto!important}}
`;
})();
