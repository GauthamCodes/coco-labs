// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Real CAD/world assets and real search events. Compare uses one scissored GL context. */
import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Scene3D, WORLD_LAYER } from '../../arena/render/scene3d';
import { loadAssetBytes } from '../../arena/mesh_cache';
import { TOKENS } from '../tokens';
import { activeTheme } from '../theme';
import { reducedMotion, readPref, isBool } from '../../prefs';
import { PREFERENCES_CHANGED } from '../../shell/settings_events';
import { QualityController, TIER_CHOICES, TIER_SETTINGS, type TierChoice } from '../../arena/render/quality';
import type { World, LoopFrame } from '../../arena/protocol';
import { type PlanStore } from '../../arena/render/planStore';
import { paneLayout } from './paneLayout';
import { comparisonBasePixels, comparisonPixels, type CostmapData, type CostLayer } from './comparisonPixels';
export interface ComparisonData { world: World; occupancy: Uint8Array; stores: PlanStore[]; costs?: CostmapData; layer?: CostLayer; difference?: boolean; revision?: number; loopFrames?: LoopFrame[] }

export function WorldStage({ kind, data, perspective = false, onReady, onHover, onGoal }: { kind: 'title' | 'compare'; data?: ComparisonData; perspective?: boolean; onReady?: () => void; onHover?: (cell: [number, number] | null) => void; onGoal?: (x: number, y: number) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [qualityNote, setQualityNote] = useState('');
  const pick = useRef<(x: number, y: number) => [number, number] | null>(() => null);
  const latest = useRef({ data, perspective, onReady, onHover, onGoal }); latest.current = { data, perspective, onReady, onHover, onGoal };
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
    const overlays: { mesh: THREE.Mesh; texture: THREE.DataTexture; pixels: Uint8Array; cursor: number; key?: string; store?: PlanStore }[] = [];
    let cachedBase: { occupancy: Uint8Array; costs?: CostmapData; layer?: CostLayer; theme: string; width: number; height: number; pixels: Uint8Array; version: number } | undefined;
    const extra = new THREE.Group(); scene.add(extra);
    const dots = new THREE.Points(new THREE.BufferGeometry(), new THREE.PointsMaterial({ color: TOKENS.computation[activeTheme()].particles, size: 4, sizeAttenuation: false, transparent: true, opacity: .5, depthWrite: false })); extra.add(dots);
    const chosenLine = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: TOKENS.computation[activeTheme()].chosen, depthTest: false })); extra.add(chosenLine);
    const ringPoints = Array.from({ length: 49 }, (_, i) => new THREE.Vector3(Math.cos(i / 48 * Math.PI * 2) * .25, Math.sin(i / 48 * Math.PI * 2) * .25, .06));
    const truthRing = new THREE.Line(new THREE.BufferGeometry().setFromPoints(ringPoints), new THREE.LineBasicMaterial({ color: TOKENS.computation[activeTheme()].truth, depthTest: false })); extra.add(truthRing);
    let rig: Scene3D | null = null;
    let quality = new QualityController(performance.now(), 'auto', 'medium');
    let motion = reducedMotion(), forceTopdown = false;
    const applyPreferences = () => {
      renderer.setClearColor(TOKENS.colours[activeTheme()].bg);
      rig?.setTheme(activeTheme());
      dots.material.color.set(TOKENS.computation[activeTheme()].particles);
      chosenLine.material.color.set(TOKENS.computation[activeTheme()].chosen);
      truthRing.material.color.set(TOKENS.computation[activeTheme()].truth);
      const choice = readPref('quality', 'auto', (value): value is TierChoice => TIER_CHOICES.includes(value as TierChoice));
      quality = new QualityController(performance.now(), choice, quality.tier);
      motion = reducedMotion(); forceTopdown = false; setQualityNote('');
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, TIER_SETTINGS[quality.tier].pixelRatioCap));
      if (rig) { rig.lowWalls = readPref('walls', false, isBool); rig.applyTier(quality.tier, renderer, scene); }
      for (const overlay of overlays) overlay.cursor = -1;
    };
    window.addEventListener(PREFERENCES_CHANGED, applyPreferences);
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
      if (disposed) { rig.dispose(); return; }
      rig.setVisible(true); rig.setPose([spec.start.x + spec.world_to_map[0], spec.start.y + spec.world_to_map[1], spec.start.theta]);
      rig.setMode('overhead', 0); rig.applyTier('medium', renderer, scene);
      applyPreferences();
      const start = performance.now(); let last = 0, nextPaint = 0;
      const draw = (now: number) => {
        if (disposed) return;
        frame = requestAnimationFrame(draw);
        if (document.hidden) { last = 0; quality.restart(now); return; }
        if (now + .1 < nextPaint) return;
        nextPaint += Math.max(1, Math.floor((now - nextPaint) / (1000 / 60)) + 1) * (1000 / 60);
        const interval = last ? now - last : 0;
        const dt = interval ? Math.min(.05, interval / 1000) : .016; last = now;
        const change = quality.frame(now, interval, true);
        if (change?.kind === 'tier') {
          rig!.applyTier(change.tier, renderer, scene);
          renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, TIER_SETTINGS[change.tier].pixelRatioCap));
        } else if (change?.kind === 'fallback' && kind === 'compare') {
          forceTopdown = true; setQualityNote(`Top-down view: ${change.reason}.`);
        }
        el.dataset.qualityTier = quality.tier;
        const bounds = el.getBoundingClientRect(); const width = bounds.width, height = bounds.height;
        if (!width || !height) return;
        const current = latest.current;
        if (kind === 'compare' && current.data) rig!.setPose(current.data.world.start);
        rig!.update(dt, width / height);
        const panes = kind === 'compare' ? current.data?.stores.length === 4 ? 4 : 2 : 1;
        const rectangles = paneLayout(panes, width, height);
        renderer.setScissorTest(true);
        for (let side = 0; side < panes; side++) {
          const { width: paneWidth, height: paneHeight, left, bottom } = rectangles[side];
          renderer.setViewport(left, bottom, paneWidth, paneHeight); renderer.setScissor(left, bottom, paneWidth, paneHeight);
          renderer.clear();
          overlays.forEach((overlay) => { overlay.mesh.visible = false; });
          let viewCamera: THREE.Camera = camera;
          if (kind === 'title') {
            const turn = motion ? 0 : (now - start) / 1000 * .035;
            const x = spec.start.x + spec.world_to_map[0], y = spec.start.y + spec.world_to_map[1];
            camera.aspect = paneWidth / paneHeight; camera.updateProjectionMatrix();
            camera.position.set(x - 1.45 * Math.cos(turn) + 1.25 * Math.sin(turn), y - 1.45 * Math.sin(turn) - 1.25 * Math.cos(turn), .95);
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
            const theme = activeTheme(), { costs, layer, difference } = current.data;
            if (!cachedBase || cachedBase.occupancy !== occupancy || cachedBase.costs !== costs || cachedBase.layer !== layer || cachedBase.theme !== theme || cachedBase.width !== world.width || cachedBase.height !== world.height) {
              cachedBase = { occupancy, costs, layer, theme, width: world.width, height: world.height,
                pixels: comparisonBasePixels(world.width, world.height, occupancy, theme, costs, layer), version: (cachedBase?.version ?? 0) + 1 };
            }
            const key = `${store.cursor}:${cachedBase.version}:${difference ? `${stores[0].cursor}:${stores[1].cursor}` : ''}`;
            if (overlay.cursor === -1 || overlay.key !== key || overlay.store !== store) {
              comparisonPixels(world.width, world.height, occupancy, store, activeTheme(), current.data.costs,
                current.data.layer, current.data.difference ? [stores[0], stores[1]] : undefined, overlay.pixels, cachedBase.pixels);
              overlay.texture.needsUpdate = true; overlay.cursor = store.cursor; overlay.key = key; overlay.store = store;
            }
            const centreX = world.origin[0] + world.width * world.resolution / 2;
            const centreY = world.origin[1] + world.height * world.resolution / 2;
            if (current.perspective && !forceTopdown) {
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
          const loop = current.data?.loopFrames?.[side];
          extra.visible = !!loop;
          if (loop) {
            rig!.setPose(loop.pose);
            truthRing.position.set(loop.truth[0], loop.truth[1], 0);
            const points = loop.particles, chosen = loop.chosen;
            const updateGeometry = (object: THREE.Points | THREE.Line, values: number[][] | null) => {
              const n = values?.[0]?.length ?? 0;
              let attribute = object.geometry.getAttribute('position') as THREE.BufferAttribute | undefined;
              if (!attribute || attribute.count < n) {
                object.geometry.dispose(); object.geometry = new THREE.BufferGeometry();
                attribute = new THREE.BufferAttribute(new Float32Array(Math.max(512, n) * 3), 3).setUsage(THREE.DynamicDrawUsage);
                object.geometry.setAttribute('position', attribute);
              }
              for (let i = 0; i < n; i++) attribute.setXYZ(i, values![0][i], values![1][i], .08);
              attribute.needsUpdate = true; object.geometry.setDrawRange(0, n); object.frustumCulled = false; object.visible = n > 0;
            };
            updateGeometry(dots, points); updateGeometry(chosenLine, chosen);
          }
          renderer.render(scene, viewCamera);
          if (kind === 'compare' && current.data) {
            const view = viewCamera; const { world } = current.data;
            pick.current = (clientX, clientY) => {
              const rect = el.getBoundingClientRect(), x = clientX - rect.left, y = rect.height - (clientY - rect.top);
              const pane = rectangles.find(p => x >= p.left && x < p.left + p.width && y >= p.bottom && y < p.bottom + p.height);
              if (!pane) return null;
              const ray = new THREE.Raycaster(); ray.setFromCamera(new THREE.Vector2((x - pane.left) / pane.width * 2 - 1, (y - pane.bottom) / pane.height * 2 - 1), view);
              const hit = ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 0, 1), 0), new THREE.Vector3());
              if (!hit) return null;
              const col = Math.floor((hit.x - world.origin[0]) / world.resolution), row = world.height - 1 - Math.floor((hit.y - world.origin[1]) / world.resolution);
              return row >= 0 && row < world.height && col >= 0 && col < world.width ? [row, col] : null;
            };
          }
        }
        if (!el.dataset.sceneReady) latest.current.onReady?.();
        el.dataset.robotPose = JSON.stringify(rig!.robotHolder.position.toArray());
        el.dataset.sceneReady = 'true'; el.dataset.glContexts = '1';
      };
      frame = requestAnimationFrame(draw);
    };
    void initialise().catch((error) => { if (!disposed) { el.dataset.sceneError = String(error); console.error(error); } });
    return () => {
      disposed = true; cancelAnimationFrame(frame); observer.disconnect();
      window.removeEventListener(PREFERENCES_CHANGED, applyPreferences);
      for (const overlay of overlays) { overlay.texture.dispose(); overlay.mesh.geometry.dispose(); (overlay.mesh.material as THREE.Material).dispose(); }
      dots.geometry.dispose(); dots.material.dispose(); chosenLine.geometry.dispose(); chosenLine.material.dispose(); truthRing.geometry.dispose(); truthRing.material.dispose();
      rig?.dispose(); renderer.dispose();
    };
  }, [kind]);
  return <><canvas className="night-world" ref={canvas} onPointerMove={event => latest.current.onHover?.(pick.current(event.clientX, event.clientY))} onPointerLeave={event => { if (event.pointerType !== 'touch') latest.current.onHover?.(null); }} onClick={event => { const cell = pick.current(event.clientX, event.clientY), world = latest.current.data?.world; if (cell && world) latest.current.onGoal?.(world.origin[0] + (cell[1] + .5) * world.resolution, world.origin[1] + (world.height - cell[0] - .5) * world.resolution); }} aria-label={kind === 'title' ? 'COCO CAD mesh idling in its existing arena; rendered presentation' : 'Compared traces in one WebGL context; click a floor cell for the shared goal'} />{qualityNote && <p className="night-quality-note" role="status">{qualityNote}</p>}</>;
}
