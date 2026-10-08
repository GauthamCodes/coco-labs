// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { StrictMode, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';

import './ui/style.css';

// Two apps, code-split: the Arena (M1) never downloads the v1 labs' code,
// and the v1 labs never download the Arena's.
const root = createRoot(document.getElementById('root')!);
const render = (node: ReactNode) => root.render(<StrictMode>{node}</StrictMode>);

if (new URLSearchParams(window.location.search).get('view') === 'arena') {
  void import('./arena/ArenaApp').then(({ ArenaApp }) => render(<ArenaApp />));
} else {
  void import('./ui/App').then(({ App }) => render(<App />));
}
