// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lens controls (M2.3+): each control sends a `config` input to the model
 * (coco_lab.arena: `key=value`), so every setting is in the run's input
 * log -- a shared link replays it, and the per-tick hashes see it. The
 * page never changes a filter itself.
 */

import { useState } from 'react';

export type Send = (choice: string) => void;

export function LocaliseControls({ send, live }: { send: Send; live: boolean }) {
  const [filter, setFilter] = useState('both');
  const [particles, setParticles] = useState(300);
  const [injection, setInjection] = useState('none');
  const [motion, setMotion] = useState(0.02);
  const [sensor, setSensor] = useState(0.02);
  const [slip, setSlip] = useState(false);
  if (!live) return <p className="lens-empty">The Localise lens runs on the live model: click the map to take over.</p>;
  return (
    <div className="lens-controls" data-testid="localise-controls" role="group" aria-label="Localisation settings">
      <label>filter <select value={filter} data-testid="loc-filter"
        onChange={(e) => { setFilter(e.target.value); send(`localise.filter=${e.target.value}`); }}>
        <option value="both">MCL and EKF</option><option value="mcl">MCL</option><option value="ekf">EKF</option><option value="off">off</option>
      </select></label>
      <label>particles <input type="number" min={10} max={2000} step={10} value={particles} data-testid="loc-particles"
        onChange={(e) => setParticles(Number(e.target.value))}
        onBlur={() => send(`localise.mcl.particles=${Math.max(10, Math.min(2000, Math.round(particles)))}`)} /></label>
      <label title="random particles put back in when the measurements fit worse than they used to (augmented MCL)">injection <select value={injection} data-testid="loc-injection"
        onChange={(e) => { setInjection(e.target.value); send(`localise.mcl.injection=${e.target.value}`); }}>
        <option value="none">none (COCO's AMCL)</option><option value="augmented">augmented</option><option value="fixed">fixed 5 %</option>
      </select></label>
      <label title="the odometry motion model's alpha1..alpha4, for the world and for both filters">motion noise
        <input type="range" min={0} max={0.2} step={0.01} value={motion} data-testid="loc-motion"
          onChange={(e) => setMotion(Number(e.target.value))}
          onPointerUp={() => { const a = [motion, motion, motion, motion].join(','); send(`arena.odom_alphas=${a}`); send(`localise.mcl.alphas=${a}`); send(`localise.ekf.alphas=${a}`); }} />
        {motion.toFixed(2)}</label>
      <label title="the LiDAR's Gaussian range noise (m)">sensor noise
        <input type="range" min={0} max={0.1} step={0.005} value={sensor} data-testid="loc-sensor"
          onChange={(e) => setSensor(Number(e.target.value))}
          onPointerUp={() => send(`arena.range_sigma=${sensor}`)} />{sensor.toFixed(3)} m</label>
      <label className="layer-toggle" title="MODEL OPTION: in turns the body rotates 0.775 of what the wheels report (Lab 2 measured COCO's wheel odometry at 72.5 rad of yaw against the truth's 56.2 on the recorded tour). Off by default.">
        <input type="checkbox" checked={slip} data-testid="loc-slip"
          onChange={(e) => { setSlip(e.target.checked); send(`arena.slip=${e.target.checked ? 'on' : 'off'}`); }} />wheel slip (model option)</label>
      <span className="lens-hint">Drag the robot to kidnap it: the filters are not told.</span>
    </div>
  );
}

export function MapControls({ send, live }: { send: Send; live: boolean }) {
  const [algorithm, setAlgorithm] = useState('occupancy');
  const [poses, setPoses] = useState('truth');
  const [particles, setParticles] = useState(20);
  const [loops, setLoops] = useState(true);
  if (!live) return <p className="lens-empty">The Map lens runs on the live model: click the map to take over.</p>;
  return (
    <div className="lens-controls" data-testid="map-controls" role="group" aria-label="Mapping settings">
      <label>algorithm <select value={algorithm} data-testid="map-algorithm"
        onChange={(e) => { setAlgorithm(e.target.value); send(`map.algorithm=${e.target.value}`); }}>
        <option value="occupancy">occupancy grid (poses given)</option>
        <option value="ekf_slam">EKF-SLAM (IDEALISED landmark sensor)</option>
        <option value="fastslam">FastSLAM</option>
        <option value="pose_graph">pose graph</option>
        <option value="off">off</option>
      </select></label>
      {algorithm === 'occupancy' && <label title="whose poses the grid is built from">poses <select value={poses} data-testid="map-poses"
        onChange={(e) => { setPoses(e.target.value); send(`map.poses=${e.target.value}`); }}>
        <option value="truth">true (known poses)</option><option value="odometry">dead reckoning</option><option value="belief">the robot's belief</option>
      </select></label>}
      {algorithm === 'fastslam' && <label>particles <input type="number" min={1} max={200} value={particles} data-testid="map-particles"
        onChange={(e) => setParticles(Number(e.target.value))}
        onBlur={() => send(`map.fastslam.particles=${Math.max(1, Math.min(200, Math.round(particles)))}`)} /></label>}
      {algorithm === 'pose_graph' && <label className="layer-toggle"><input type="checkbox" checked={loops} data-testid="map-loops"
        onChange={(e) => { setLoops(e.target.checked); send(`map.pose_graph.loop_closure=${e.target.checked ? 'on' : 'off'}`); }} />loop closure</label>}
      {algorithm === 'ekf_slam' && <span className="lens-hint">The landmark sensor is IDEALISED: obstacle corners with known identities. COCO has none.</span>}
      <span className="lens-hint">Changing a setting starts the map again. Drive somewhere: the map is built as COCO moves.</span>
    </div>
  );
}

const SCENARIO_TITLES: [string, string][] = [
  ['none', 'your own goals'],
  ['static_room', 'Lab 5: the hairpin (round a wall end, into a room)'],
  ['crossing', 'Lab 5: a person crosses the path'],
  ['oncoming', 'Lab 5: a person walks head-on down the path'],
  ['mislocalised', 'Lab 5: run 15 — believes it is 3.4 m away'],
];

export function MoveControls({ send, live }: { send: Send; live: boolean }) {
  const [controller, setController] = useState('dwa');
  const [scenario, setScenario] = useState('none');
  if (!live) return <p className="lens-empty">The Move lens runs on the live model: click the map to take over.</p>;
  return (
    <div className="lens-controls" data-testid="move-controls" role="group" aria-label="Local control settings">
      <label>controller <select value={controller} data-testid="move-controller"
        onChange={(e) => { setController(e.target.value); send(`move.controller=${e.target.value}`); }}>
        <option value="dwa">DWA (after DWB)</option><option value="rpp">regulated pure pursuit</option>
        <option value="mppi">MPPI</option><option value="builtin">M1's waypoint driver</option>
      </select></label>
      <label>scenario <select value={scenario} data-testid="move-scenario"
        onChange={(e) => { setScenario(e.target.value); send(`move.scenario=${e.target.value}`); }}>
        {SCENARIO_TITLES.map(([id, t]) => <option key={id} value={id}>{t}</option>)}
      </select></label>
      <span className="lens-hint">MODEL controllers, written after Lab 5's. Here the actors are solid; in Lab 5's Gazebo runs they had no collision body.</span>
    </div>
  );
}
