// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import type { Footprint, LadderRung } from '../bundle/load';
import type { Swept } from '../lab/footprint';

export interface LadderProps {
  ladder: LadderRung[];
  currentId: string | null;
  onRung: (id: string) => void;
  sweep: boolean;
  onSweep: (on: boolean) => void;
  footprint: Footprint | undefined;
  swept: Swept | null;
}

/**
 * The map ladder: the same kind of question asked of ever more real maps —
 * a teaching grid, the arena's walls, then Nav2's own inflated costmap —
 * with COCO's footprint swept along the path once the map has a scale.
 */
export function Ladder({ ladder, currentId, onRung, sweep, onSweep, footprint, swept }: LadderProps) {
  return (
    <section className="ladder" aria-labelledby="ladder-h" data-testid="ladder">
      <h2 id="ladder-h">Map ladder</h2>
      <ol className="rungs">
        {ladder.map((r) => (
          <li key={r.id}>
            <button type="button" className={currentId === r.id ? 'rung active' : 'rung'}
              aria-current={currentId === r.id ? 'step' : undefined}
              onClick={() => onRung(r.id)} data-testid={`rung-${r.rung}`}>
              <span className="rung-n">{r.rung}</span> {r.title}
            </button>
            <span className="note">{r.note}</span>
          </li>
        ))}
      </ol>
      <label className="choice">
        <input type="checkbox" checked={sweep} onChange={(e) => onSweep(e.target.checked)} data-testid="sweep" />
        Sweep COCO's footprint along the path
      </label>
      {sweep && footprint && (
        <p className="note" data-testid="sweep-note">
          {swept && !swept.placed ? `Not drawn: ${swept.reason}. ` : ''}
          Footprint {footprint.length_m} m × {footprint.width_m} m, {footprint.derivation} ({footprint.source}).
        </p>
      )}
    </section>
  );
}
