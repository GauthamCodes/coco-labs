// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { useEffect, useState } from 'react';
import { Info, Settings } from 'lucide-react';
import { HeroStage } from '../game/HeroStage';
import { warmModel } from '../arena/worker_pool';
import { navigate } from '../ui/navigation';
import { openSettings } from './settings_events';
import '../game/fonts.css';
import '../game/game.css';
const BASE = import.meta.env.BASE_URL;

/**
 * G1.2: the title. G2.7: "COCO Lab · a ROS 2 robot you can drive in your browser" and a line of
 * plain-text badges (no logos); the ⓘ says what is model and what is recorded.
 * A full-bleed 3D hero shot of COCO in the Depot, the logo, one big
 * PLAY and three smaller doors (Compare, Research, Learn). A small ⓘ says what is real.
 * The model warms only after the first scene has drawn, at idle or on first input (M5
 * review decision 1); any key plays.
 */
export function TitleScreen() {
  const [ready, setReady] = useState(false);
  const [info, setInfo] = useState(false);
  useEffect(() => { document.title = 'COCO Lab'; }, []);
  useEffect(() => {
    if (!ready) return;
    let idle: number | undefined;
    let started = false;
    const start = () => { if (started) return; started = true; warmModel(); };
    window.addEventListener('pointerdown', start, { once: true });
    window.addEventListener('keydown', start, { once: true });
    const frame = requestAnimationFrame(() => { if ('requestIdleCallback' in window) idle = window.requestIdleCallback(start); });
    return () => {
      cancelAnimationFrame(frame);
      if (idle !== undefined) window.cancelIdleCallback(idle);
      window.removeEventListener('pointerdown', start);
      window.removeEventListener('keydown', start);
    };
  }, [ready]);
  useEffect(() => {
    let started = false;
    const play = (event: KeyboardEvent) => {
      if (started || event.repeat || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || ['Tab', 'Shift', 'Escape', 'Control', 'Alt', 'Meta'].includes(event.key)) return;
      if (event.target instanceof Element && event.target.closest('a,button,input,select,textarea,dialog')) return;
      started = true; event.preventDefault();
      navigate(`${BASE}?view=play`);
    };
    window.addEventListener('keydown', play); return () => window.removeEventListener('keydown', play);
  }, []);
  const doors = [{ label: 'Compare', copy: 'See algorithms race', view: 'compare' }, { label: 'Research', copy: 'Real ROS 2 recordings', view: 'research' }, { label: 'Learn', copy: 'Guided tours', view: 'learn' }];
  return <main className="g1" data-testid="title" data-g1="title" data-ready={ready ? 'true' : 'false'} style={{ touchAction: 'manipulation' }}>
    <HeroStage onReady={() => setReady(true)} />
    <div className="g1-title-top">
      <button className="g1-icon g1-glass" aria-label="Settings" onClick={openSettings}><Settings size={20} /></button>
      <button className="g1-icon g1-glass" aria-label="What is real here" aria-expanded={info} onClick={() => setInfo((x) => !x)}><Info size={20} /></button>
      <a className="g1-icon g1-glass" href={`${BASE}?view=about`} aria-label="About COCO Lab" style={{ color: 'inherit', fontWeight: 700, textDecoration: 'none' }}>?</a>
    </div>
    {info && <div className="g1-sheet g1-glass" role="note" style={{ top: 'calc(64px + env(safe-area-inset-top))' }}>
      <h3>WHAT IS REAL HERE</h3>
      <p><b>MODEL</b> · in your browser: a model of COCO's ROS 2 stack (Play, Compare). Its topic names, frames and message shapes mirror the real stack — you can even save a run as a rosbag2 file — but the browser does not run ROS 2. COCO is a kinematic model: no physics engine.</p>
      <p><b>STACK</b> · recorded: the real ROS 2 stack (Nav2, MoveIt) driving COCO in Gazebo Harmonic (Research › Recordings).</p>
      <p><b>REMOTE</b> · the simulated stack over the internet (About › Live).</p>
      <p><b>HARDWARE</b> · a physical robot. None exists.</p>
    </div>}
    <div className="g1-title-bottom">
      <div className="g1-title-copy"><h1 className="g1-logo" aria-label="COCO Lab">COCO<span>·</span>LAB</h1><p className="g1-tag">a ROS 2 robot you can drive in your browser</p>
        <p className="g2-badges" data-testid="title-badges" aria-label="What COCO Lab is built from">Model of COCO's ROS 2 stack · Nav2 · Gazebo Harmonic · MoveIt <button className="g2-badges-i" onClick={() => setInfo((x) => !x)} aria-label="What is model and what is recorded">ⓘ</button></p></div>
      <a className="g1-big" href={`${BASE}?view=play`} data-testid="title-play" aria-label="Play: drive COCO">▶ PLAY</a>
      <nav className="g1-cards" aria-label="Other modes">{doors.map((d) => <a key={d.view} className="g1-card g1-glass" href={`${BASE}?view=${d.view}`}><h3>{d.label}</h3><p>{d.copy}</p></a>)}</nav>
    </div>
  </main>;
}
