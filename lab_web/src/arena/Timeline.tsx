// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The timeline panel (M1.7): the world track (ticks) and the computation
 * track (events of the search shown at that tick), with play, pause, step,
 * speed and scrub. It only reads and sets ArenaSession; it draws nothing
 * else.
 */

import { useEffect, useState } from 'react';

import { SPEEDS, type ArenaSession } from './session';

export function Timeline({ session }: { session: ArenaSession | null }) {
  const [, setN] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setN((n) => n + 1), 100);
    return () => clearInterval(t);
  }, []);
  if (!session) return null;
  const shown = session.shownTick;
  const first = session.history[0]?.tick ?? 0;
  const s = session.shownSearch;
  const seq = s ? (session.viewSeq ?? s.cursor) : 0;
  return (
    <section className="timeline" aria-label="Timeline" data-testid="timeline">
      <div className="arena-row">
        <button type="button" className="seg-btn" data-testid="tl-play" aria-pressed={session.playing}
          onClick={() => { session.playing = !session.playing; }}>{session.playing ? 'Pause' : 'Play'}</button>
        <button type="button" className="seg-btn" data-testid="tl-back" aria-label="Step one tick back"
          onClick={() => session.stepTick(-1)}>−1 tick</button>
        <button type="button" className="seg-btn" data-testid="tl-fwd" aria-label="Step one tick forward"
          onClick={() => session.stepTick(+1)}>+1 tick</button>
        <label>speed{' '}
          <select value={session.speed} data-testid="tl-speed" onChange={(e) => session.setSpeed(Number(e.target.value))}>
            {SPEEDS.map((v) => <option key={v} value={v}>{v}×</option>)}
          </select>
        </label>
        <button type="button" className={session.live ? 'seg-btn active' : 'seg-btn'} data-testid="tl-live"
          aria-pressed={session.live} onClick={() => session.goLive()}>live</button>
      </div>
      <label className="track">
        <span>world · tick {shown?.tick ?? 0} · t = {(shown?.t_world ?? 0).toFixed(1)} s</span>
        <input type="range" min={first} max={Math.max(first, session.head)} step={1} value={shown?.tick ?? 0}
          data-testid="tl-world" aria-label="World track (ticks)"
          onChange={(e) => { session.playing = false; session.seekTick(Number(e.target.value)); }} />
      </label>
      <label className="track">
        <span>computation · {s ? `${s.planner} search ${s.searchId}: event ${seq.toLocaleString()} of ${s.received.toLocaleString()}` : 'no search at this tick'}</span>
        <input type="range" min={0} max={s?.received ?? 0} step={1} value={seq} disabled={!s}
          data-testid="tl-seq" aria-label="Computation track (events within the tick)"
          onChange={(e) => { session.playing = false; session.seekSeq(Number(e.target.value)); }} />
        <span className="arena-row">
          <button type="button" className="seg-btn" data-testid="tl-seq-back" disabled={!s} onClick={() => session.stepSeq(-1)}>−1 event</button>
          <button type="button" className="seg-btn" data-testid="tl-seq-fwd" disabled={!s} onClick={() => session.stepSeq(+1)}>+1 event</button>
        </span>
      </label>
    </section>
  );
}
