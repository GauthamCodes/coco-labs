// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import type { SettingsAnalysis } from '../bundle/load';
import type { DecodedBundle } from '../bundle/model';
import { COST_QUESTION } from '../lab/predict';
import {
  ALGORITHM_NAMES, analysisFor, boundFor, describeBound, sameAsBundle, type SearchSettings,
} from '../lab/settings';
import { PredictQuestion } from './Predict';

const HEURISTIC_NAMES: Record<string, string> = {
  zero: 'zero (h = 0)', manhattan: 'Manhattan', euclidean: 'Euclidean', octile: 'octile',
};
const TIE_NAMES: Record<string, string> = {
  low_h: 'prefer lower h (deeper)', fifo: 'first in, first out',
};

export interface SettingsPanelProps {
  analysis: SettingsAnalysis;
  bundle: DecodedBundle;
  value: SearchSettings;
  onChange: (s: SearchSettings) => void;
  onRun: () => void;
  locked: string | null;
  busy: boolean;
  prediction: string | null;
  onPrediction: (v: string | null) => void;
}

/**
 * The five algorithms and their knobs. The admissibility / consistency badge
 * and the suboptimality bound are coco_lab's own verdicts, looked up in the
 * table the site was built with; the search runs in coco_lab when you press
 * Run.
 */
export function SettingsPanel({ analysis: sa, bundle, value, onChange, onRun, locked, busy, prediction,
  onPrediction }: SettingsPanelProps) {
  const set = (patch: Partial<SearchSettings>) => onChange({ ...value, ...patch });
  const m = analysisFor(sa, bundle, value.connectivity, value.heuristic);
  const bound = m ? boundFor(sa, m, value.algorithm, value.weight) : undefined;
  const wi = Math.max(0, sa.weights.indexOf(value.weight));
  const usesH = value.algorithm === 'astar' || value.algorithm === 'weighted_astar' || value.algorithm === 'greedy';
  const unchanged = sameAsBundle(value, bundle);

  return (
    <section className="settings" aria-labelledby="settings-h" data-testid="settings">
      <h2 id="settings-h">Search settings</h2>
      {locked && <p className="note" data-testid="settings-locked">{locked}</p>}
      <fieldset disabled={!!locked || busy}>
        <label className="field">
          <span>Algorithm</span>
          <select data-testid="set-algorithm" value={value.algorithm} onChange={(e) => set({ algorithm: e.target.value })}>
            {sa.algorithms.map((a) => <option key={a} value={a}>{ALGORITHM_NAMES[a] ?? a}</option>)}
          </select>
        </label>

        <label className="field">
          <span>Heuristic</span>
          <select data-testid="set-heuristic" value={value.heuristic} onChange={(e) => set({ heuristic: e.target.value })}>
            {sa.heuristics.map((h) => <option key={h} value={h}>{HEURISTIC_NAMES[h] ?? h}</option>)}
          </select>
        </label>
        {m ? (
          <p className={m.admissible ? 'badge ok' : 'badge bad'} data-testid="heuristic-badge">
            <strong>{m.admissible ? 'Admissible and consistent' : 'Not admissible, not consistent'}</strong>
            {' '}on {value.connectivity}-connectivity. <span className="why">{m.reason}.</span>
            {!usesH && <span className="why"> {ALGORITHM_NAMES[value.algorithm]} does not use it to decide; its values are still shown on hover.</span>}
          </p>
        ) : (
          <p className="badge" data-testid="heuristic-badge">coco_lab did not analyse this move model.</p>
        )}

        <div className="field" role="radiogroup" aria-label="Connectivity">
          <span>Moves</span>
          {([4, 8] as const).map((c) => (
            <label key={c} className="choice">
              <input type="radio" name="conn" checked={value.connectivity === c}
                onChange={() => set({ connectivity: c })} data-testid={`set-conn-${c}`} />
              {c}-connected
            </label>
          ))}
        </div>

        <div className="field" role="radiogroup" aria-label="Tie-breaking">
          <span>Ties</span>
          {sa.tie_breaks.map((t) => (
            <label key={t} className="choice">
              <input type="radio" name="tie" checked={value.tieBreak === t}
                onChange={() => set({ tieBreak: t })} data-testid={`set-tie-${t}`} />
              {TIE_NAMES[t] ?? t}
            </label>
          ))}
        </div>

        <label className="field weight">
          <span>Weight w = {sa.weights[wi].toFixed(2)}</span>
          <input type="range" min={0} max={sa.weights.length - 1} step={1} value={wi}
            disabled={value.algorithm !== 'weighted_astar'} data-testid="set-weight"
            aria-valuetext={`w = ${sa.weights[wi]}`}
            onChange={(e) => set({ weight: sa.weights[Number(e.target.value)] })} />
        </label>
        {value.algorithm !== 'weighted_astar' && (
          <p className="note">
            The weight applies to weighted A* only: f = g + w·h. w = 0 is Dijkstra and w = 1 is A*, event for
            event <span className="cite">(coco_lab/test/test_properties.py: test_weight_zero_reproduces_dijkstra,
            test_weight_one_reproduces_astar)</span>.
          </p>
        )}

        <p className="bound" data-testid="bound">
          <strong>Guarantee:</strong> {describeBound(value.algorithm, bound)}
        </p>
        <p className="cite">Verdicts: {sa.by}. Tested in {sa.cite}.</p>

        {!unchanged && (
          <PredictQuestion id="cost" question={COST_QUESTION.question} options={COST_QUESTION.options}
            value={prediction} onChange={onPrediction} />
        )}
        <button type="button" className="run" onClick={onRun} disabled={!!locked || busy || unchanged}
          data-testid="run-settings">
          {unchanged ? 'These are the shown settings' : 'Run with these settings'}
        </button>
      </fieldset>
    </section>
  );
}
