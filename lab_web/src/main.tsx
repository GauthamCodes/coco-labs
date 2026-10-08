// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { StrictMode, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';

import './ui/style.css';

// Two apps, code-split: the Arena (M1) never downloads the v1 labs' code,
// and the v1 labs never download the Arena's.
const root = createRoot(document.getElementById('root')!);
const render = (node: ReactNode) => root.render(<StrictMode>{node}</StrictMode>);

// The Arena is the landing page (M1.10, once every agent-measured M1
// criterion passed). Every v1 link either names its view (`?view=plan`,
// `?view=live`, ...) or is a v1 share link (`?bundle=`, `?v=`), and keeps
// opening v1 exactly as before.
const q = new URLSearchParams(window.location.search);
if (q.get('view') === 'arena' || (!q.has('view') && !q.has('bundle') && !q.has('v'))) {
  void import('./arena/ArenaApp').then(({ ArenaApp }) => render(<ArenaApp />));
} else {
  void import('./ui/App').then(({ App }) => render(<App />));
}
