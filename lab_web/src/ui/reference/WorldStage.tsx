// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Real CAD/world assets and real search events. Compare uses one scissored GL context. */
import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { Scene3D, WORLD_LAYER } from '../../arena/render/scene3d';
import { loadAssetBytes } from '../../arena/mesh_cache';
import { TOKENS } from '../tokens';
import { activeTheme } from '../theme';
import { reducedMotion } from '../../prefs';
import type { World } from '../../arena/protocol';
import { CLOSED, FRONTIER, PATH, type PlanStore } from '../../arena/render/planStore';
export interface ComparisonData { world: World; occupancy: Uint8Array; stores: [PlanStore, PlanStore] }

export function WorldStage({ kind, data, perspective = false }: { kind: 'title' | 'compare'; data?: ComparisonData; perspective?: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const latest = useRef({ data, perspective }); latest.current = { data, perspective };
  useEffect(() => {
    const el = canvas.current!;
    let disposed = false, frame = 0;
    const renderer = new THREE.WebGLRenderer({ canvas: el, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.setClearColor(TOKENS.colours[activeTheme()].bg);
    renderer.autoClear = false;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, .03, 150);
    camera.up.set(0, 0, 1); camera.layers.enable(WORLD_LAYER);
    const overhead = new THREE.OrthographicCamera(-1, 1, 1, -1, .01, 150);
    overhead.up.set(0, 1, 0); overhead.layers.enable(WORLD_LAYER);
    const overlays: { mesh: THREE.Mesh; texture: THREE.DataTexture; pixels: Uint8Array; cursor: number }[] = [];
    let rig: Scene3D | null = null;
    let spec: { world_to_map: [number, number]; start: { x: number; y: number; theta: number } };
    const base = import.meta.env.BASE_URL;
    const resize = () => {
      const bounds = el.getBoundingClientRect();
      if (bounds.width > 0 && bounds.height > 0) renderer.setSize(bounds.width, bounds.height, false);
    };
    const observer = new ResizeObserver(resize); observer.observe(el); resize();
    const initialise = async () => {
      spec = await (await fetch(base + 'generated/arena/coco_arena_v1.json', { credentials: 'omit' })).json();
      if (disposed) return;
      rig = new Scene3D(scene, spec.world_to_map);
      await rig.load({ arena: base + 'assets3d/arena.glb', robot: base + 'assets3d/robot_low.glb', buffers: {
        arena: loadAssetBytes(base + 'assets3d/arena.glb'), robot: loadAssetBytes(base + 'assets3d/robot_low.glb'),
      } });
      if (disposed) return;
      rig.setVisible(true); rig.setPose([spec.start.x, spec.start.y, spec.start.theta]);
      rig.setMode('overhead', 0); rig.applyTier('medium', renderer, scene);
      const start = performance.now(); let last = 0, nextPaint = 0;
      const draw = (now: number) => {
        if (disposed) return;
        frame = requestAnimationFrame(draw);
        if (document.hidden || now + .1 < nextPaint) return;
        nextPaint += Math.max(1, Math.floor((now - nextPaint) / (1000 / 60)) + 1) * (1000 / 60);
        const dt = last ? Math.min(.05, (now - last) / 1000) : .016; last = now;
        const bounds = el.getBoundingClientRect(); const width = bounds.width, height = bounds.height;
        if (!width || !height) return;
        rig!.update(dt, width / height);
        const current = latest.current;
        const portrait = width < height;
        const panes = kind === 'compare' ? 2 : 1;
        renderer.setScissorTest(true);
        for (let side = 0; side < panes; side++) {
          const paneWidth = panes === 2 && !portrait ? width / 2 : width;
          const paneHeight = panes === 2 && portrait ? height / 2 : height;
          const left = !portrait ? side * paneWidth : 0;
          const bottom = portrait && panes === 2 ? (1 - side) * paneHeight : 0;
          renderer.setViewport(left, bottom, paneWidth, paneHeight); renderer.setScissor(left, bottom, paneWidth, paneHeight);
          renderer.clear();
          overlays.forEach((overlay) => { overlay.mesh.visible = false; });
          let viewCamera: THREE.Camera = camera;
          if (kind === 'title') {
            const turn = reducedMotion() ? 0 : (now - start) / 1000 * .035;
            const x = spec.start.x, y = spec.start.y;
            camera.aspect = paneWidth / paneHeight; camera.updateProjectionMatrix();
            camera.position.set(x - 1.45 * Math.cos(turn), y - 1.25 * Math.cos(turn), .95);
            camera.lookAt(x, y, .18);
          } else if (current.data) {
            const { world, stores, occupancy } = current.data;
            const store = stores[side];
            if (!overlays[side]) {
              const pixels = new Uint8Array(world.width * world.height * 4);
              const texture = new THREE.DataTexture(pixels, world.width, world.height);
              texture.magFilter = THREE.NearestFilter; texture.minFilter = THREE.NearestFilter;
              texture.colorSpace = THREE.SRGBColorSpace;
              const mesh = new THREE.Mesh(new THREE.PlaneGeometry(world.width * world.resolution, world.height * world.resolution), new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false }));
              mesh.position.set(world.origin[0] + world.width * world.resolution / 2, world.origin[1] + world.height * world.resolution / 2, .025);
              mesh.renderOrder = 10; scene.add(mesh); overlays[side] = { mesh, texture, pixels, cursor: -1 };
            }
            const overlay = overlays[side]; overlay.mesh.visible = true;
            if (overlay.cursor !== store.cursor) {
              const p = TOKENS.computation[activeTheme()];
              const bytes = (hex: string) => [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16));
              const colours = [null, bytes(p.frontier), bytes(p.closed), bytes(p.path)];
              const solid = bytes(p.occupied);
              for (let row = 0; row < world.height; row++) for (let col = 0; col < world.width; col++) {
                const index = row * world.width + col, pixel = ((world.height - 1 - row) * world.width + col) * 4;
                const state = store.state[index]; const colour = colours[state] ?? solid;
                overlay.pixels[pixel] = colour[0];
                overlay.pixels[pixel + 1] = colour[1];
                overlay.pixels[pixel + 2] = colour[2];
                overlay.pixels[pixel + 3] = state === CLOSED ? Math.round(p.closedAlpha * 255) : state === FRONTIER || state === PATH ? 255 : occupancy[index] ? 75 : 0;
              }
              overlay.texture.needsUpdate = true; overlay.cursor = store.cursor;
            }
            const centreX = world.origin[0] + world.width * world.resolution / 2;
            const centreY = world.origin[1] + world.height * world.resolution / 2;
            if (current.perspective) {
              camera.aspect = paneWidth / paneHeight; camera.updateProjectionMatrix();
              camera.position.set(centreX - 10, centreY - 12, 16); camera.lookAt(centreX, centreY, 0);
            } else {
              const mapWidth = world.width * world.resolution, mapHeight = world.height * world.resolution;
              const halfHeight = Math.max(mapHeight, mapWidth / (paneWidth / paneHeight)) * .56;
              overhead.left = -halfHeight * paneWidth / paneHeight; overhead.right = -overhead.left;
              overhead.top = halfHeight; overhead.bottom = -halfHeight; overhead.updateProjectionMatrix();
              overhead.position.set(centreX, centreY, 30); overhead.lookAt(centreX, centreY, 0); viewCamera = overhead;
            }
          }
          renderer.render(scene, viewCamera);
        }
        el.dataset.sceneReady = 'true'; el.dataset.glContexts = '1';
      };
      frame = requestAnimationFrame(draw);
    };
    void initialise().catch((error) => { if (!disposed) { el.dataset.sceneError = String(error); console.error(error); } });
    return () => {
      disposed = true; cancelAnimationFrame(frame); observer.disconnect();
      for (const overlay of overlays) { overlay.texture.dispose(); overlay.mesh.geometry.dispose(); (overlay.mesh.material as THREE.Material).dispose(); }
      rig?.dispose(); renderer.dispose();
    };
  }, [kind]);
  return <canvas className="night-world" ref={canvas} aria-label={kind === 'title' ? 'COCO CAD mesh idling in its existing arena; rendered presentation' : 'Two real planner traces in one WebGL context'} />;
}
