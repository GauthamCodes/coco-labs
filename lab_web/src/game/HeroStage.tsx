// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.2: the title's hero shot: COCO in the Depot under the lights, a slow
 * camera move. No model runs here (nothing moves but the camera and the
 * forklift beacons): the scene is the level's look and COCO's real model at
 * the level's start pose. Presentation only.
 */

import { useEffect, useRef } from 'react';
import { GameRenderer } from './render/GameRenderer';
import { describe, type Spec } from './world/describe';
import { pickTier } from './tier';

const BASE = import.meta.env.BASE_URL;

export function HeroStage({ onReady }: { onReady?: () => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const tier = pickTier() === 'high' ? 'medium' : pickTier();
    const r = new GameRenderer(canvas.current!, tier);
    let alive = true, raf = 0, last = performance.now();
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    void (async () => {
      const spec = await (await fetch(`${BASE}generated/arena/coco_depot_v1.json`, { credentials: 'omit' })).json() as Spec & { start: { x: number; y: number; theta: number } };
      const look = describe(spec);
      await r.loadWorld(look, `${BASE}generated/g1/depot.light.png`);
      // COCO by the dispatch floor, facing the dock lights
      r.pose = [spec.start.x + spec.world_to_map[0], spec.start.y + spec.world_to_map[1], 0.35];
      r.setLed('auto');
      await r.loadRobot(`${BASE}assets3d/robot_low.glb`);
      if (!alive) return;
      r.cam.setMode('orbit');
      r.cam.orbit.dist = 2.4; r.cam.orbit.pitch = 0.32; r.cam.orbit.yaw = -2.4;
      const frame = (now: number) => {
        raf = requestAnimationFrame(frame);
        const dt = Math.min(0.1, (now - last) / 1000);
        last = now;
        if (!reduced) r.cam.orbit.yaw += dt * 0.08;
        r.frame(dt);
      };
      r.frame(0);
      canvas.current!.dataset.sceneReady = 'true';
      onReady?.();
      raf = requestAnimationFrame(frame);
    })().catch(() => { if (canvas.current) canvas.current.dataset.sceneReady = 'true'; onReady?.(); });
    const resize = () => r.resize();
    window.addEventListener('resize', resize);
    return () => { alive = false; cancelAnimationFrame(raf); window.removeEventListener('resize', resize); r.dispose(); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return <canvas ref={canvas} className="g1-canvas" data-scene-ready="false" aria-label="COCO in the Depot at night" />;
}
