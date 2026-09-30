// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { BRUSH_SIZES, type Tool } from '../lab/brush';

export interface ToolsProps {
  editable: boolean;
  tool: Tool;
  brush: number;
  onTool: (t: Tool) => void;
  onBrush: (b: number) => void;
}

const TOOL_NAMES: Record<Tool, string> = { look: 'Look', paint: 'Paint wall', erase: 'Erase' };

/**
 * Brush painting. "Look" leaves the map to hover and, on a phone, to
 * scrolling; "Paint wall" and "Erase" turn a drag into one stroke, which
 * coco_lab applies and searches again in the worker.
 */
export function Tools({ editable, tool, brush, onTool, onBrush }: ToolsProps) {
  if (!editable) {
    return <p className="edit-note">Recorded runs are shown as recorded; they are not editable.</p>;
  }
  return (
    <div className="tools" role="group" aria-label="Map tools" data-testid="tools">
      <div className="seg" role="radiogroup" aria-label="Tool">
        {(Object.keys(TOOL_NAMES) as Tool[]).map((t) => (
          <button key={t} type="button" role="radio" aria-checked={tool === t}
            className={tool === t ? 'seg-btn active' : 'seg-btn'} data-testid={`tool-${t}`}
            onClick={() => onTool(t)}>{TOOL_NAMES[t]}</button>
        ))}
      </div>
      <label className="brush">
        <span>Brush</span>
        <select value={brush} onChange={(e) => onBrush(Number(e.target.value))} data-testid="brush"
          disabled={tool === 'look'}>
          {BRUSH_SIZES.map((b) => <option key={b} value={b}>{b} × {b}</option>)}
        </select>
      </label>
      <p className="edit-note">
        {tool === 'look'
          ? 'Choose Paint wall or Erase, then drag across the map. coco_lab reruns the search in your browser (Python via Pyodide) when you let go — the page never searches itself.'
          : 'Drag across the map; the search reruns when you let go. The start and the goal cannot be painted over.'}
      </p>
    </div>
  );
}
