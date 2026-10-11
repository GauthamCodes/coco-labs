// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { StrictMode, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';

import { needsRunIds, route, type Route } from './landing';
import './ui/style.css';

// Three apps, code-split: the Arena (M1), Learn (M2.8) and the Live view
// (kept in `main` until M5). The v1 lab views are retired (M2.10): a v1
// link goes to its Learn mission, to its converted run in the Arena, or
// to the frozen v1 build at v1/ with its query intact (landing.ts).
const root = createRoot(document.getElementById('root')!);
const render = (node: ReactNode) => root.render(<StrictMode>{node}</StrictMode>);
const BASE = import.meta.env.BASE_URL;

function go(r: Route) {
  if ('redirect' in r) {
    window.location.replace(`${BASE}${r.redirect}`);
  } else if (r.app === 'arena') {
    void import('./arena/ArenaApp').then(({ ArenaApp }) => render(<ArenaApp />));
  } else if (r.app === 'learn') {
    void import('./learn/LearnApp').then(({ LearnApp }) => render(<LearnApp />));
  } else if (r.app === 'casefiles') {
    void import('./casefiles/CaseFilesApp').then(({ CaseFilesApp }) => render(<CaseFilesApp />));
  } else if (r.app === 'play') {
    void import('./play/PlayApp').then(({ PlayApp }) => render(<PlayApp />));
  } else {
    void import('./ui/LiveApp').then(({ LiveApp }) => render(<LiveApp />));
  }
}

const search = window.location.search;
if (needsRunIds(search)) {
  // a Lab 1 link: open its converted run if this site serves it, else v1 recomputes it
  void fetch(`${BASE}generated/v2/index.json`, { credentials: 'omit' })
    .then((r) => (r.ok ? r.json() : { runs: [] }))
    .then((j: { runs?: { id: string }[] }) => new Set((j.runs ?? []).map((x) => x.id)))
    .catch(() => null)
    .then((ids) => go(route(search, __LANDING__, ids)));
} else {
  go(route(search, __LANDING__));
}
