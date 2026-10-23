// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { Fragment, StrictMode, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { needsRunIds, route } from './landing';
import { GlobalSettings } from './shell/GlobalSettings';
import { navigate } from './ui/navigation';
import { applyTheme, isTheme } from './ui/theme';
import { decodeChallenge, urlFieldError } from './links/bounds.mjs';
import './ui/style.css';
import { registerStaticCache } from './offline/register';
import { countVisit } from './offline/counter';
import { VISIT_COUNTER_ID } from '../site.config';
import '@fontsource-variable/outfit';
import '@fontsource-variable/manrope';
applyTheme();
const root = createRoot(document.getElementById('root')!);
const BASE = import.meta.env.BASE_URL;
const render = (node: ReactNode) => root.render(<StrictMode><Fragment key={window.location.search}>{node}</Fragment><GlobalSettings /></StrictMode>);
let generation = 0;
async function display() {
  const ownGeneration = ++generation;
  const search = window.location.search, params = new URLSearchParams(search);
  const requestedTheme = params.get('theme');
  if (isTheme(requestedTheme)) applyTheme(requestedTheme);
  const reference = params.get('reference');
  let node: ReactNode;
  if (['title', 'play', 'compare'].includes(reference ?? '') && !['run', 'replay', 'casefile', 'play', 'c', 'l', 's', 'z'].some(key => params.has(key))) {
    const { ReferenceScreens } = await import('./ui/reference/ReferenceScreens'); node = <ReferenceScreens />;
  } else {
    let ids: Set<string> | null = null;
    if (needsRunIds(search)) {
      try { const response = await fetch(`${BASE}generated/v2/index.json`, { credentials: 'omit' });
        const data = await response.json() as { runs?: { id: string }[] }; ids = new Set((data.runs ?? []).map(run => run.id));
      } catch { /* no index: route to the frozen archive rather than guess */ }
    }
    const destination = route(search, __LANDING__, ids);
    if (ownGeneration !== generation) return;
    if ('redirect' in destination) {
      const target = new URL(BASE + destination.redirect, window.location.href);
      if (target.pathname !== BASE) { window.location.replace(target.href); return; }
      window.history.replaceState(null, '', target); await display(); return;
    }
    let linkError = urlFieldError(params);
    if (!linkError && (params.has('s') || params.has('z'))) {
      try { decodeChallenge(params); } catch (error) { linkError = String((error as Error).message); }
    }
    if (linkError) {
      if (ownGeneration === generation) render(<main><p role="alert">Share link refused: {linkError}</p></main>);
      return;
    }
    switch (destination.app) {
      case 'title': { const { TitleScreen } = await import('./shell/TitleScreen'); node = <TitleScreen />; break; }
      case 'about': { const { AboutPage } = await import('./shell/AboutPage'); node = <AboutPage />; break; }
      case 'compare': { const { CompareWorkspace } = await import('./compare/CompareWorkspace'); node = <CompareWorkspace />; break; }
      case 'arena': { const { ArenaApp } = await import('./arena/ArenaApp'); node = <ArenaApp />; break; }
      case 'learn': { const { LearnApp } = await import('./learn/LearnApp'); node = <LearnApp />; break; }
      case 'casefiles': { const { CaseFilesApp } = await import('./casefiles/CaseFilesApp'); node = <CaseFilesApp />; break; }
      case 'play': { const { PlayApp } = await import('./play/PlayApp'); node = <PlayApp />; break; }
      case 'live': { const { LiveApp } = await import('./ui/LiveApp'); node = <LiveApp />; break; }
    }
  }
  if (ownGeneration === generation) render(node);
}
const show = () => void display().catch(error => render(<main><p role="alert">Could not open COCO Lab: {String(error)}</p></main>));
window.addEventListener('popstate', show);
document.addEventListener('click', event => {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
  if (!(event.target instanceof Element)) return;
  const anchor = event.target.closest<HTMLAnchorElement>('a[href]');
  if (!anchor || anchor.target || anchor.hasAttribute('download')) return;
  const url = new URL(anchor.href);
  if (url.origin !== location.origin || url.pathname !== BASE || (url.hash && url.search === location.search)) return;
  event.preventDefault(); navigate(url.pathname + url.search + url.hash);
});
registerStaticCache();
countVisit(VISIT_COUNTER_ID);
show();
