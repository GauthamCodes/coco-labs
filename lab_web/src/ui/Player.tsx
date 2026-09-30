// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef } from 'react';

export const SPEEDS = [1, 10, 100, 1000, 10000];

export interface PlayerProps {
  n: number;
  k: number;
  playing: boolean;
  speed: number;
  reducedMotion: boolean;
  onSeek: (k: number) => void;
  onPlaying: (p: boolean) => void;
  onSpeed: (s: number) => void;
}

/**
 * Play, pause, step, scrub, speed. Keyboard: Space plays/pauses, ←/→ step
 * one event, Shift+←/→ step 100. With `prefers-reduced-motion` nothing
 * autoplays, and play advances in discrete jumps (no per-frame animation).
 */
export function Player({ n, k, playing, speed, reducedMotion, onSeek, onPlaying, onSpeed }: PlayerProps) {
  const kRef = useRef(k);
  kRef.current = k;
  // keep the ref current between a seek and the re-render it causes, so the
  // next frame never reads a stale position
  const seekRef = useRef(onSeek);
  seekRef.current = onSeek;

  useEffect(() => {
    if (!playing) return;
    const onSeek = (v: number) => {
      kRef.current = v;
      seekRef.current(v);
    };
    if (kRef.current >= n) onSeek(0);
    if (reducedMotion) {
      const jump = Math.max(speed * 30, Math.ceil(n / 20));
      const id = window.setInterval(() => {
        const next = Math.min(n, kRef.current + jump);
        onSeek(next);
        if (next >= n) onPlaying(false);
      }, 600);
      return () => window.clearInterval(id);
    }
    let raf = 0;
    const tick = () => {
      const next = Math.min(n, kRef.current + speed);
      onSeek(next);
      if (next >= n) onPlaying(false);
      else raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, n, reducedMotion, onPlaying]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === 'SELECT' || t.tagName === 'TEXTAREA' ||
        (t.tagName === 'INPUT' && (t as HTMLInputElement).type !== 'range'))) return;
      if (e.code === 'Space') {
        if (t && t.tagName === 'BUTTON') return; // the focused button handles its own Space
        e.preventDefault();
        onPlaying(!playing);
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault();
        const d = (e.key === 'ArrowRight' ? 1 : -1) * (e.shiftKey ? 100 : 1);
        onPlaying(false);
        onSeek(Math.max(0, Math.min(n, kRef.current + d)));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [n, playing, onSeek, onPlaying]);

  const step = (d: number) => {
    onPlaying(false);
    onSeek(Math.max(0, Math.min(n, k + d)));
  };

  return (
    <div className="player" role="group" aria-label="Trace player">
      <div className="player-buttons">
        <button type="button" onClick={() => step(-100)} aria-label="Back 100 events">«</button>
        <button type="button" onClick={() => step(-1)} aria-label="Back one event">‹</button>
        <button type="button" className="play" onClick={() => onPlaying(!playing)}
          aria-label={playing ? 'Pause' : 'Play'} data-testid="play">{playing ? 'Pause' : 'Play'}</button>
        <button type="button" onClick={() => step(1)} aria-label="Forward one event">›</button>
        <button type="button" onClick={() => step(100)} aria-label="Forward 100 events">»</button>
        <label className="speed">
          <span>events/frame</span>
          <select value={speed} onChange={(e) => { const v = Number(e.target.value); if (v > 0) onSpeed(v); }} aria-label="Speed">
            {SPEEDS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
      </div>
      <input className="scrub" type="range" min={0} max={n} step={1} value={k} aria-label="Scrub"
        data-testid="scrub" onChange={(e) => { onPlaying(false); onSeek(Number(e.target.value)); }} />
      <div className="player-pos" aria-live="off">event {k.toLocaleString('en')} of {n.toLocaleString('en')}</div>
    </div>
  );
}
