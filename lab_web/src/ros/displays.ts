// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.2: SIM view's displays, by RViz's names (README §1; G2 prompt §2.1/§2.3). Each draws
 * something the browser model computed (MODEL): nothing here is RViz or ROS 2, the names only
 * teach what a ROS user would see in RViz for the same moment. Saved in prefs ('displays').
 */

export type DisplayId = 'grid' | 'robot' | 'tf' | 'scan' | 'map' | 'global_costmap' | 'local_costmap' | 'global_plan' | 'local_plan' | 'footprint' | 'goal';

export interface DisplayState { on: boolean; color?: string; size?: number; alpha?: number }
export type Displays = Record<DisplayId, DisplayState>;

export interface DisplayDef {
  id: DisplayId;
  /** RViz's display type, as its Displays panel names it */
  rviz: string;
  /** the model topic or frame it draws (M6F.7 names) */
  source: string;
  /** what the model computed, in one line */
  what: string;
  defaults: DisplayState;
  /** which options the panel offers */
  options: ('color' | 'size' | 'alpha')[];
}

export const DISPLAYS: DisplayDef[] = [
  { id: 'grid', rviz: 'Grid', source: 'map', what: 'A metric grid on the map frame: 1 m major, 0.1 m minor cells.', defaults: { on: true, color: '#a0a0a4', alpha: 0.5 }, options: ['color', 'alpha'] },
  { id: 'robot', rviz: 'RobotModel', source: '/tf, /tf_static', what: "COCO's URDF model, posed by the model's frames and joint states.", defaults: { on: true, alpha: 1 }, options: ['alpha'] },
  { id: 'tf', rviz: 'TF', source: '/tf, /tf_static', what: 'Every frame as RGB axes (x red, y green, z blue) with its name.', defaults: { on: true, size: 0.3 }, options: ['size'] },
  { id: 'scan', rviz: 'LaserScan', source: '/scan', what: "The model's 480 LiDAR beams as points, coloured by range.", defaults: { on: true, size: 0.05, alpha: 1 }, options: ['size', 'alpha'] },
  { id: 'map', rviz: 'Map', source: '/map', what: "The saved map (nav_msgs/OccupancyGrid): free, occupied, unknown.", defaults: { on: true, alpha: 0.85 }, options: ['alpha'] },
  { id: 'global_costmap', rviz: 'Map (Global Costmap)', source: 'model costmap', what: "The model's layered costmap (static, LiDAR obstacles, inflation), in RViz's costmap palette.", defaults: { on: true, alpha: 0.22 }, options: ['alpha'] },
  { id: 'local_costmap', rviz: 'Map (Local Costmap)', source: 'model costmap', what: 'The same costmap in a 3 × 3 m window that moves with COCO, as Nav2’s local costmap does.', defaults: { on: true, alpha: 0.35 }, options: ['alpha'] },
  { id: 'global_plan', rviz: 'Path (Global Plan)', source: '/plan', what: "The planner's path (nav_msgs/Path).", defaults: { on: true, color: '#19ff00' }, options: ['color'] },
  { id: 'local_plan', rviz: 'Path (Local Plan)', source: '/cmd_vel', what: "Where the current command (v, ω) takes COCO in the next second. The model's waypoint follower samples no candidate trajectories, so none are drawn.", defaults: { on: true, color: '#ff4040' }, options: ['color'] },
  { id: 'footprint', rviz: 'Polygon (Footprint)', source: 'robot radius', what: "COCO's footprint: a circle of the model's robot radius.", defaults: { on: true, color: '#00ff00' }, options: ['color'] },
  { id: 'goal', rviz: 'Pose (Goal)', source: 'goal', what: "The goal COCO is driving to, as an arrow (its heading: the plan's last leg).", defaults: { on: true, color: '#ff1900' }, options: ['color'] },
];

export const DISPLAY_IDS = DISPLAYS.map((d) => d.id);

/** G2.9: the costmaps start off on phones (semi-transparent overlays, toggled in Displays). */
export const PHONE_OFF: DisplayId[] = ['global_costmap', 'local_costmap'];

export function defaultDisplays(phone = false): Displays {
  const d = Object.fromEntries(DISPLAYS.map((x) => [x.id, { ...x.defaults }])) as Displays;
  if (phone) for (const id of PHONE_OFF) d[id].on = false;
  return d;
}

const HEX = /^#[0-9a-f]{6}$/i;
const unit = (v: unknown) => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1;

/** Read saved displays, keeping only valid fields; anything missing takes its default. */
export function parseDisplays(raw: unknown, phone = false): Displays {
  const out = defaultDisplays(phone);
  if (!raw || typeof raw !== 'object') return out;
  for (const d of DISPLAYS) {
    const s = (raw as Record<string, unknown>)[d.id];
    if (!s || typeof s !== 'object') continue;
    const r = s as Record<string, unknown>;
    if (typeof r.on === 'boolean') out[d.id].on = r.on;
    if (d.options.includes('color') && typeof r.color === 'string' && HEX.test(r.color)) out[d.id].color = r.color;
    if (d.options.includes('alpha') && unit(r.alpha)) out[d.id].alpha = r.alpha as number;
    if (d.options.includes('size') && typeof r.size === 'number' && Number.isFinite(r.size) && r.size > 0 && r.size <= 1) out[d.id].size = r.size;
  }
  return out;
}

export const isDisplays = (v: unknown): v is Displays => !!v && typeof v === 'object';
