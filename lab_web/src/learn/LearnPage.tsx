// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1.7: the Learn door's page -- the seven missions as cards. Each keeps its guided
 * tour (unchanged, in Compare) and links to a pre-made experiment that asks the
 * mission's question over many scenarios instead of one. The graded course is R4.
 * Experiments are MODEL results; where a mission's subject is not yet an experiment
 * family (mapping, search), its card asks a related question and says so.
 */
import { useEffect, useState } from 'react';
import { ModeNav } from '../ui/ModeNav';
import { experimentLink } from '../workbench/links';
import type { ExperimentSpec } from '../workbench/spec';
import '../workbench/workbench.css';
import '../game/fonts.css';
const BASE = import.meta.env.BASE_URL;

interface Mission { id: string; number: number; title: string; question: string }
const S = 'coco.experiment.v1' as const;

/** The pre-made experiment for each mission: the question, the spec, and what it is honest about. */
export const MISSION_EXPERIMENTS: Record<string, { ask: string; spec: ExperimentSpec; note?: string }> = {
  'find-a-path': { ask: 'Is A* always faster than Dijkstra? Run it on 50 scenarios.',
    spec: { schema: S, title: 'Is A* always faster than Dijkstra?', world: 'coco_arena_v1', family: 'planning', seed: 1,
      algorithms: [{ name: 'astar' }, { name: 'dijkstra' }], scenarios: { kind: 'suite', id: 'arena-nav-50' } } },
  'world-changes': { ask: 'Does D* Lite\'s first plan expand fewer cells than A*? 100 Depot pairs.',
    spec: { schema: S, title: 'D* Lite against A*: the first plan', world: 'coco_depot_v1', family: 'planning', seed: 1,
      algorithms: [{ name: 'astar' }, { name: 'dstar_lite' }], scenarios: { kind: 'suite', id: 'depot-nav-100' } },
    note: 'A first plan only: D* Lite\'s advantage is repair after a change, which this experiment does not measure.' },
  'where-it-is': { ask: 'After a kidnap, does MCL with injection recover more often than plain MCL or the EKF?',
    spec: { schema: S, title: 'Recovering from a kidnap', world: 'coco_arena_v1', family: 'localisation', seed: 1,
      algorithms: [{ name: 'mcl', params: { 'mcl.particles': 60, 'mcl.beams': 12 } }, { name: 'mcl_augmented', params: { 'mcl.particles': 60, 'mcl.beams': 12 } },
        { name: 'ekf', params: { 'ekf.beams': 12 } }], scenarios: { kind: 'sampled', n: 10, seed: 3, min_separation_m: 4 },
      limits: { max_ticks: 1500 }, options: { kidnap_at_s: 8 } } },
  'build-a-map': { ask: 'How wide must a passage be? Sweep the robot radius over the workshop maze and the rack aisles.',
    spec: { schema: S, title: 'Robot radius against narrow passages', world: 'coco_depot_v1', family: 'planning', seed: 1,
      algorithms: [{ name: 'astar' }], scenarios: { kind: 'suite', id: 'depot-narrow-30' },
      sweep: { params: [{ name: 'robot_radius', values: [0.2, 0.25, 0.3, 0.35, 0.4, 0.45] }] } },
    note: 'Mapping is not an experiment family yet (R6); this asks about the map the planner sees.' },
  'avoid-things': { ask: 'Which local controller reaches the goal most often? DWA, Regulated Pure Pursuit and MPPI on 10 pairs.',
    spec: { schema: S, title: 'Local controllers on the Proving Ground', world: 'coco_arena_v1', family: 'control', seed: 1,
      algorithms: [{ name: 'dwa' }, { name: 'rpp' }, { name: 'mppi' }], scenarios: { kind: 'sampled', n: 10, seed: 7, min_separation_m: 3 },
      limits: { max_ticks: 1500 } } },
  'where-to-look': { ask: 'Greedy best-first looks only at the goal: is it fast, and how much longer are its paths?',
    spec: { schema: S, title: 'Greedy best-first against A*', world: 'coco_depot_v1', family: 'planning', seed: 1,
      algorithms: [{ name: 'astar' }, { name: 'greedy' }], scenarios: { kind: 'suite', id: 'depot-nav-100' } },
    note: 'Search for an object is not an experiment family yet; this asks how a goal-directed search trades effort for path length.' },
  'why-did-it-fail': { ask: 'How often does each controller fail in the tight places, and how? Open the failures.',
    spec: { schema: S, title: 'Controller failures in the narrow Depot', world: 'coco_depot_v1', family: 'control', seed: 1,
      algorithms: [{ name: 'builtin' }, { name: 'dwa' }, { name: 'rpp' }], scenarios: { kind: 'suite', id: 'depot-narrow-30' },
      limits: { max_ticks: 3000 } } },
};

export function LearnPage() {
  const [missions, setMissions] = useState<Mission[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { document.title = 'Learn · COCO Lab'; }, []);
  useEffect(() => {
    let alive = true;
    fetch(`${BASE}generated/missions.json`, { credentials: 'omit' }).then((r) => { if (!r.ok) throw new Error(`missions: HTTP ${r.status}`); return r.json(); })
      .then((d: { missions: Mission[] }) => { if (alive) setMissions(d.missions); }).catch((e) => { if (alive) setError(String(e)); });
    return () => { alive = false; };
  }, []);
  const site = new URL(BASE, window.location.href).href;
  return <main className="wb" data-testid="learn-page">
    <ModeNav current="learn" evidence="MODEL" />
    <header className="wb-head"><p className="eyebrow">LEARN</p><h1>Seven questions about how a robot thinks.</h1>
      <p>Each mission is a guided tour of one question, with its claims and evidence. Then test it yourself: every mission links to an experiment that asks the same question over many scenarios. Experiments run the model in your browser (MODEL); the tours point to real ROS 2 recordings (STACK).</p></header>
    <section className="wb-section">
      {error && <p role="alert">{error}</p>}
      {!missions && !error && <p role="status">Loading the missions…</p>}
      <div className="wb-cards">{missions?.map((m) => { const x = MISSION_EXPERIMENTS[m.id]; return <article className="wb-card" key={m.id} data-mission={m.id}>
        <p className="eyebrow">MISSION {m.number}</p><h3>{m.title}</h3><p>{m.question}</p>
        {x && <p><b>Try it:</b> {x.ask}</p>}
        {x?.note && <p className="wb-muted">{x.note}</p>}
        <a href={`${BASE}?view=learn&mission=${m.id}`}>Take the tour</a>
        {x && <a href={experimentLink(x.spec, site)} data-testid={`learn-experiment-${m.id}`}>Run the experiment</a>}
      </article>; })}</div>
    </section>
  </main>;
}
