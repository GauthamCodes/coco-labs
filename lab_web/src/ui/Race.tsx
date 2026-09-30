// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useMemo, useState } from 'react';

import { cursorAtStep, expansionEnds, raceRow } from '../lab/race';
import { ALGORITHM_NAMES } from '../lab/settings';
import type { Current } from './App';
import { MapView } from './MapView';
import { Player } from './Player';

export interface RaceSetupProps {
  algorithms: string[];
  chosen: string[];
  onChosen: (a: string[]) => void;
  onStart: () => void;
  disabled: string | null;
  busy: boolean;
}

/** Pick two to four algorithms; they run on identical inputs. */
export function RaceSetup({ algorithms, chosen, onChosen, onStart, disabled, busy }: RaceSetupProps) {
  const toggle = (a: string) => onChosen(chosen.includes(a) ? chosen.filter((x) => x !== a)
    : algorithms.filter((x) => chosen.includes(x) || x === a));
  const ok = chosen.length >= 2 && chosen.length <= 4;
  return (
    <section className="race-setup" aria-labelledby="race-h" data-testid="race-setup">
      <h2 id="race-h">Race</h2>
      {disabled && <p className="note">{disabled}</p>}
      <fieldset disabled={!!disabled || busy}>
        <p className="note">Two to four algorithms, one map, one start and goal, and the heuristic, ties and weight above.</p>
        {algorithms.map((a) => (
          <label key={a} className="choice">
            <input type="checkbox" checked={chosen.includes(a)} onChange={() => toggle(a)}
              data-testid={`race-${a}`} disabled={!chosen.includes(a) && chosen.length >= 4} />
            {ALGORITHM_NAMES[a] ?? a}
          </label>
        ))}
        <button type="button" className="run" onClick={onStart} disabled={!ok} data-testid="race-start">
          {ok ? `Race ${chosen.length}` : 'Choose two to four'}
        </button>
      </fieldset>
    </section>
  );
}

export interface RaceViewProps {
  entrants: Current[];
  optimalCost: number | null;
  reducedMotion: boolean;
  onClose: () => void;
}

const pct = (x: number) => `${x >= 0 ? '+' : ''}${(x * 100).toFixed(1)} %`;
const num = (x: number | null, d = 2) => (x === null ? '—' : x.toFixed(d));

/**
 * The race: one pane per algorithm, advanced together by a shared counter of
 * EXPANSIONS, and the final table. Every number is from the trace summaries
 * coco_lab wrote; the optimum is coco_lab's Dijkstra on the same inputs.
 */
export function RaceView({ entrants, optimalCost, reducedMotion, onClose }: RaceViewProps) {
  const ends = useMemo(() => entrants.map((e) => expansionEnds(e.bundle.trace.events, e.bundle.trace.n)), [entrants]);
  const maxStep = Math.max(...ends.map((e) => e.length));
  const [step, setStep] = useState(maxStep);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(10);
  const [hover, setHover] = useState<[number, number] | null>(null);
  const rows = entrants.map((e) => raceRow(e.bundle, optimalCost));

  return (
    <section className="race" aria-label="Race" data-testid="race">
      <div className="race-head">
        <h2>Race on identical inputs</h2>
        <button type="button" onClick={onClose} data-testid="race-close">Back to one search</button>
      </div>
      <div className={`race-grid n${entrants.length}`}>
        {entrants.map((e, i) => {
          const k = cursorAtStep(ends[i], e.bundle.trace.n, step);
          const done = step >= ends[i].length;
          return (
            <figure key={e.bundle.contentHash} className="race-pane" data-testid="race-pane">
              <figcaption>
                <strong>{ALGORITHM_NAMES[e.bundle.trace.header.algorithm]}</strong>
                {' '}<span className="note">{done ? 'finished' : `${Math.min(step, ends[i].length)} expanded`}</span>
              </figcaption>
              <MapView bundle={e.bundle} k={k} hover={hover} onHover={setHover} />
            </figure>
          );
        })}
      </div>
      <Player n={maxStep} k={step} playing={playing} speed={speed} reducedMotion={reducedMotion} unit="expansions"
        onSeek={setStep} onPlaying={setPlaying} onSpeed={setSpeed} />
      <table className="race-table" data-testid="race-table">
        <thead>
          <tr><th>Algorithm</th><th>Expansions</th><th>Cost</th><th>Length</th><th>Gap to optimal</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.algorithm}>
              <td>{ALGORITHM_NAMES[r.algorithm] ?? r.algorithm}</td>
              <td>{r.expansions}</td>
              <td>{r.status === 'found' ? num(r.cost, 3) : 'no path'}</td>
              <td>{r.length === null ? '—' : `${num(r.length, 2)} ${r.lengthUnit}`}</td>
              <td>{r.gap === null ? '—' : pct(r.gap)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="cite">
        Optimum: {optimalCost === null ? 'no path' : optimalCost.toFixed(3)}, from coco_lab's Dijkstra on the same map,
        start, goal and move model. Cost and length are each trace's summary; length is in {rows[0]?.lengthUnit}.
      </p>
    </section>
  );
}
