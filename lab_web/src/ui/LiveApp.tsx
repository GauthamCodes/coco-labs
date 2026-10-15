// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Live view's page (`?view=live`), kept in `main` until M5 (M2 prompt,
 * M2.10). It was one tab of the v1 lab app; the lab views are retired, so
 * the page is now the Live view alone, unchanged, with links to the Arena,
 * Learn and the frozen v1 build.
 */

import { useState } from 'react';

import { LiveView } from './LiveView';
import { Settings } from 'lucide-react';
import { openSettings } from '../shell/settings_events';

const BASE = import.meta.env.BASE_URL;

export function LiveApp() {
  const [liveText, setLiveText] = useState('Live Stack (simulated) — local');
  return (
    <div className="app">
      <header className="top">
        <h1>COCO Lab <span className="sub">Live Stack (simulated)</span></h1>
        <nav className="views" aria-label="Views">
          <a className="seg-btn" href={`${BASE}?view=arena`} data-testid="nav-arena">Play · Free roam</a>
          <a className="seg-btn" href={`${BASE}?view=compare`} data-testid="nav-learn">Compare</a>
          <a className="seg-btn" href={`${BASE}?view=about`}>About</a>
          <button className="seg-btn" aria-label="Settings" onClick={openSettings}><Settings size={20}/></button>
        </nav>
        <span className="mode-badge mode-live" data-testid="mode-badge">{liveText}</span>
      </header>
      <LiveView onLabel={setLiveText} />
    </div>
  );
}
