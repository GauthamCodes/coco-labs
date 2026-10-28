// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2 honesty about ROS (the G2 prompt §0, "critical"): the browser runs a ROS 2-shaped Python
 * model, not ROS 2. So no text the site ships says the browser runs ROS 2; every ROS-looking
 * surface carries its label (MODEL, or STACK for recordings); no shipped asset is a ROS, Gazebo,
 * RViz, Nav2, MoveIt or NVIDIA logo (they are named in plain text only).
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { REPO } from './helpers';

const SRC = join(REPO, 'lab_web', 'src');
function files(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? files(p) : /\.(tsx?|css|html|json)$/.test(f) ? [p] : [];
  });
}
const ALL = files(SRC).map((p) => ({ p: p.slice(REPO.length + 1), text: readFileSync(p, 'utf-8') }));
/** what is shown or saved: string literals and JSX text, not comments */
const shown = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');

describe('the browser never claims to run ROS 2', () => {
  it('no shipped text says the browser runs ROS 2', () => {
    const bad = /\b(running|runs|run on|powered by) ROS ?2\b|\bROS ?2 (is )?running\b|\breal ROS ?2 in (your|the) browser\b/i;
    const hits = ALL.flatMap(({ p, text }) => shown(text).split('\n').filter((l) => bad.test(l) && !/\bnot\b|\bno ROS 2\b|\bnever\b/i.test(l)).map((l) => `${p}: ${l.trim()}`));
    expect(hits).toEqual([]);
  });

  it('the ROS-looking surfaces say MODEL', () => {
    const must: [string, RegExp][] = [
      ['lab_web/src/game/panels/Panels.tsx', /ROS 2 graph \(model of COCO's stack\)/],
      ['lab_web/src/game/panels/Panels.tsx', /<b>MODEL<\/b>/],
      ['lab_web/src/game/PlayGame.tsx', /SIM · RViz-style view of the browser model <b>MODEL<\/b>/],
      ['lab_web/src/game/hud/RosHud.tsx', /\/rosout \(model events\)/],
      ['lab_web/src/game/hud/RosHud.tsx', /Telemetry \(model\)/],
      ['lab_web/src/game/hud/PlannerInset.tsx', /<b>MODEL<\/b>/],
      ['lab_web/src/ros/bag.ts', /\['evidence', 'MODEL'\]/],
      ['lab_web/src/game/GameApp.tsx', /· MODEL/],
      ['lab_web/src/shell/TitleScreen.tsx', /does not run ROS 2/],
    ];
    for (const [p, re] of must) expect(re.test(ALL.find((f) => f.p === p)!.text), `${p} ${re}`).toBe(true);
  });

  it('the model graph is labelled MODEL where it comes from', () => {
    const g = JSON.parse(readFileSync(join(REPO, 'docs', 'v2', 'm6', 'data', 'ros_graph.json'), 'utf-8')) as { evidence: string };
    expect(g.evidence).toBe('MODEL');
  });

  it('no shipped asset is a ROS, Gazebo, RViz, Nav2, MoveIt or NVIDIA logo', () => {
    const m = JSON.parse(readFileSync(join(REPO, 'docs', 'v2', 'DESIGN_ASSETS.json'), 'utf-8')) as { assets: unknown };
    const names = JSON.stringify(m.assets).toLowerCase();
    for (const brand of ['ros-logo', 'ros_logo', 'gazebo', 'rviz', 'nav2', 'moveit', 'nvidia', 'isaac']) expect(names, brand).not.toContain(brand);
    const pub = join(REPO, 'lab_web', 'public');
    const shipped = (d: string): string[] => readdirSync(d).flatMap((f) => (statSync(join(d, f)).isDirectory() ? shipped(join(d, f)) : [f.toLowerCase()]));
    const imgs = shipped(pub).filter((f) => /\.(png|svg|jpe?g|webp|ico)$/.test(f));
    expect(imgs.filter((f) => /ros|gazebo|rviz|nav2|moveit|nvidia|isaac/.test(f))).toEqual([]);
  });
});
