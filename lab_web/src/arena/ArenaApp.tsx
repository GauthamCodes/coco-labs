// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { lazy, Suspense } from 'react';

const PlayScene = lazy(() => import('./PlayScene'));
const CompareScene = lazy(() => import('./CompareScene'));
const ResearchScene = lazy(() => import('./ResearchScene'));

/** Existing Arena URLs retain their presentation; M5.5 migrates mode navigation. */
export function ArenaApp() {
  const params = new URLSearchParams(window.location.search);
  const Shell = params.has('play') ? PlayScene : params.has('casefile') || params.has('replay') || params.has('run') ? ResearchScene
    : params.has('mission') || params.has('lens') || params.has('compare') ? CompareScene : PlayScene;
  return <Suspense fallback={null}><Shell /></Suspense>;
}
