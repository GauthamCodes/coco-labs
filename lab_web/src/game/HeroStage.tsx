// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.2: the title's hero shot: COCO in the Depot under the lights, a slow
 * camera move. No model runs here (nothing moves but the camera and the
 * forklift beacons): the scene is the level's look and COCO's real model at
 * the level's start pose. Presentation only.
 *
 * G2.9 (Gautham's review: the title sat on the robot in landscape): the orbit looks at COCO, so
 * COCO is drawn at the canvas centre; a vertical view offset moves the drawn picture so COCO sits
 * in the middle of the band left free between the top icons and the title text, on every screen.
 */

import { useEffect, useRef } from 'react';
import { GameRenderer } from './render/GameRenderer';
import { describe, type Spec } from './world/describe';
import { pickTier } from './tier';

const BASE = import.meta.env.BASE_URL;

/** The view offset (px, + moves the picture up) that centres COCO in the band above the title. */
export function heroShift(h: number, bandTop: number, bandBottom: number): number {
  if (!(bandBottom > bandTop) || h <= 0) return 0;
  return Math.round(h / 2 - (bandTop + bandBottom) / 2);
}

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
      let placedAt = -1e9;
      const frame = (now: number) => {
        raf = requestAnimationFrame(frame);
        if (now - placedAt > 500) { placedAt = now; place(); }   // fonts and the layout settle after load
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
    const place = () => {
      const c = canvas.current;
      if (!c) return;
      const w = c.clientWidth, h = c.clientHeight;
      const top = document.querySelector('.g1-title-top')?.getBoundingClientRect();
      const copy = document.querySelector('.g1-title-copy')?.getBoundingClientRect();
      const shift = heroShift(h, top ? top.bottom + 4 : 0, copy ? copy.top - 6 : h);
      const cam = r.cam.camera;
      if (cam.view?.enabled && cam.view.offsetY === shift && cam.view.fullHeight === h && cam.view.fullWidth === w) return;
      if (shift) cam.setViewOffset(w, h, 0, shift, w, h); else cam.clearViewOffset();
    };
    const resize = () => { r.resize(); place(); };
    window.addEventListener('resize', resize);
    return () => { alive = false; cancelAnimationFrame(raf); window.removeEventListener('resize', resize); r.dispose(); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return <canvas ref={canvas} className="g1-canvas" data-scene-ready="false" aria-label="COCO in the Depot at night" />;
}
