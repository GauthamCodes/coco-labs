// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** R1: the Workbench's tabs; Recordings is today's library at ?view=research, unchanged. R2: Algorithm Studio. R3.5: Model vs ROS 2. */
import './workbench.css';
const BASE = import.meta.env.BASE_URL;

export type Tab = 'studio' | 'experiments' | 'benchmarks' | 'leaderboard' | 'gap' | 'recordings' | 'datasets';
export const TABS: { id: Tab; label: string; href: string }[] = [
  { id: 'studio', label: 'Algorithm Studio', href: '?view=workbench&tab=studio' },
  { id: 'experiments', label: 'Experiments', href: '?view=workbench' },
  { id: 'benchmarks', label: 'Benchmarks', href: '?view=workbench&tab=benchmarks' },
  { id: 'leaderboard', label: 'Leaderboard', href: '?view=workbench&tab=leaderboard' },
  { id: 'gap', label: 'Model vs ROS 2', href: '?view=workbench&tab=gap' },
  { id: 'recordings', label: 'Recordings', href: '?view=research' },
  { id: 'datasets', label: 'Datasets', href: '?view=workbench&tab=datasets' },
];

export function WorkbenchTabs({ current }: { current: Tab }) {
  return <nav className="wb-tabs" aria-label="Workbench">{TABS.map((t) => <a key={t.id} href={`${BASE}${t.href}`} aria-current={t.id === current ? 'page' : undefined} data-testid={`wb-tab-${t.id}`}>{t.label}</a>)}</nav>;
}
