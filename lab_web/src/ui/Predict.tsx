// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import type { Reveal } from '../lab/predict';

export interface PredictProps {
  id: string;
  question: string;
  options: Array<[string, string]>; // [value, label]
  value: string | null;
  onChange: (v: string | null) => void;
}

/** One question before a run. Answering is optional. */
export function PredictQuestion({ id, question, options, value, onChange }: PredictProps) {
  return (
    <fieldset className="predict" data-testid={`predict-${id}`}>
      <legend>{question}</legend>
      {options.map(([v, label]) => (
        <label key={v} className="choice">
          <input type="radio" name={`predict-${id}`} checked={value === v} onChange={() => onChange(v)}
            data-testid={`predict-${id}-${v}`} />
          {label}
        </label>
      ))}
      <label className="choice">
        <input type="radio" name={`predict-${id}`} checked={value === null} onChange={() => onChange(null)} />
        Skip
      </label>
    </fieldset>
  );
}

/** The measured answer, beside the prediction. */
export function RevealNote({ reveal }: { reveal: Reveal }) {
  return (
    <div className={`reveal ${reveal.right === null ? '' : reveal.right ? 'right' : 'wrong'}`} data-testid="reveal"
      role="status">
      <strong>{reveal.question}</strong>{' '}
      {reveal.predicted !== null && (
        <span>You predicted <em>{reveal.predicted}</em>{reveal.right ? ' — right.' : ' — not this time.'} </span>
      )}
      <span>Measured: {reveal.measured}</span>
      <span className="cite"> (from the trace summaries coco_lab wrote for these runs)</span>
    </div>
  );
}
