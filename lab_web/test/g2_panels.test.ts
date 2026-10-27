// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.4: the panels' logic -- Topic echo prints as `ros2 topic echo` does (YAML, long arrays cut
 * with a count); a topic counts a message only when the model produced one (ros_graph's rates);
 * saved displays are validated field by field (prefs never break SIM view).
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { defaultDisplays, DISPLAYS, parseDisplays } from '../src/ros/displays';
import { topicsOf, TopicStats, type Frame } from '../src/ros/recorder';
import { STACK_NODES } from '../src/ros/stack';
import { twistStamped } from '../src/ros/shapes';
import { toYaml } from '../src/ros/yaml';

const frame = (o: Partial<Frame> = {}): Frame => ({ tick: 1, t: 0.1, pose: [0, 0, 0], v: 0, w: 0, source: 'idle', tf: null, ranges: new Float32Array(4), plan: null, goal: null, teleop: null, arm: null, ...o });

describe('Topic echo', () => {
  it('prints YAML as ros2 topic echo does', () => {
    expect(toYaml(twistStamped(0.25, -0.5, 67.6))).toBe([
      'header:', '  stamp:', '    sec: 67', '    nanosec: 600000000', "  frame_id: ''",
      'twist:', '  linear:', '    x: 0.25', '    y: 0', '    z: 0', '  angular:', '    x: 0', '    y: 0', '    z: -0.5'].join('\n'));
  });

  it('cuts a long array to its first values and a count; infinities as YAML .inf', () => {
    const y = toYaml({ ranges: [1, 2, Infinity, 4, 5, 6, 7, 8, 9, 10], intensities: [] }, 3);
    expect(y).toBe(['ranges:', '- 1', '- 2', '- .inf', "- '... 7 more (10 values)'", 'intensities: []'].join('\n'));
  });
});

describe('the ROS 2 graph panel', () => {
  it('counts only the messages the model produced', () => {
    expect(topicsOf(frame(), true)).toEqual(['/scan', '/odom', '/tf', '/cmd_vel', '/map', '/tf_static']);
    expect(topicsOf(frame({ source: 'planner', plan: [[1, 1]] }), false)).toEqual(['/scan', '/odom', '/tf', '/cmd_vel', '/cmd_vel_nav', '/plan']);
    expect(topicsOf(frame({ source: 'teleop', teleop: [0.3, 0] }), false)).toEqual(['/scan', '/odom', '/tf', '/cmd_vel', '/cmd_vel_teleop']);
  });

  it('measures a rate from arrivals (wall clock)', () => {
    const s = new TopicStats();
    for (let k = 0; k <= 20; k++) s.mark('/scan', k * 100, k * 0.1);
    expect(s.rate('/scan', 2000)).toBeCloseTo(10, 6);
    expect(s.rate('/plan', 2000)).toBeNull();
    expect(s.last('/scan', 2050)).toEqual({ sim: 2, agoMs: 50 });
  });

  it('names a Stack counterpart (with its source file) for every node of the model graph', () => {
    const graph = JSON.parse(readFileSync(new URL('../../docs/v2/m6/data/ros_graph.json', import.meta.url), 'utf-8')) as { nodes: string[] };
    for (const n of graph.nodes) {
      expect(STACK_NODES[n], n).toBeTruthy();
      expect(STACK_NODES[n].source.length).toBeGreaterThan(3);
    }
  });
});

describe('Displays', () => {
  it('are RViz\'s display types, all on by default', () => {
    expect(DISPLAYS.map((d) => d.rviz)).toEqual(['Grid', 'RobotModel', 'TF', 'LaserScan', 'Map', 'Map (Global Costmap)', 'Map (Local Costmap)', 'Path (Global Plan)', 'Path (Local Plan)', 'Polygon (Footprint)', 'Pose (Goal)']);
    expect(Object.values(defaultDisplays()).every((d) => d.on)).toBe(true);
  });

  it('a saved value is used only where valid', () => {
    const d = parseDisplays({ scan: { on: false, size: 0.1, alpha: 7 }, grid: { color: 'red' }, nope: { on: false } });
    expect(d.scan.on).toBe(false);
    expect(d.scan.size).toBe(0.1);
    expect(d.scan.alpha).toBe(1);            // 7 refused: the default stays
    expect(d.grid.color).toBe('#a0a0a4');    // not a hex colour: the default stays
    expect(parseDisplays('garbage')).toEqual(defaultDisplays());
  });

  it('G2.9: on a phone the costmaps start off (overlays, toggled in Displays); a saved choice wins', () => {
    const d = defaultDisplays(true);
    expect(d.global_costmap.on).toBe(false);
    expect(d.local_costmap.on).toBe(false);
    expect(Object.entries(d).filter(([k]) => !k.endsWith('costmap')).every(([, v]) => v.on)).toBe(true);
    expect(parseDisplays({ global_costmap: { on: true } }, true).global_costmap.on).toBe(true);
    // semi-transparent overlays by default
    expect(d.global_costmap.alpha).toBeLessThan(0.5);
    expect(d.local_costmap.alpha).toBeLessThan(0.5);
  });
});
