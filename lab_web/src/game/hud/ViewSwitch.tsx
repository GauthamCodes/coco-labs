// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.2: the GAME | SIM switch (top right; V on a keyboard). Two views of the same moment:
 * GAME is G1's look with the robotics cues always on; SIM draws the model's ROS-shaped state
 * the way RViz draws a ROS 2 robot. Switching is instant, keeps the run going and never
 * changes the model.
 */

import type { View } from '../render/GameRenderer';

export function ViewSwitch({ view, onView, desktop }: { view: View; onView: (v: View) => void; desktop: boolean }) {
  return <div className="g2-view g1-glass" role="group" aria-label="View (V): GAME or SIM" data-testid="g2-view" data-view={view}>
    <button aria-pressed={view === 'game'} data-testid="g2-view-game" onClick={() => onView('game')}
      aria-label="GAME view: the game look, with COCO's sensing and plan">GAME</button>
    <button aria-pressed={view === 'sim'} data-testid="g2-view-sim" onClick={() => onView('sim')}
      aria-label="SIM view: the same moment as RViz would show it (model of COCO's ROS 2 stack)">SIM</button>
    {desktop && <kbd>V</kbd>}
  </div>;
}
