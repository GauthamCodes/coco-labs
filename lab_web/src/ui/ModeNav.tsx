// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Play, Learn, Compare and Workbench share navigation and an evidence badge
 * (R1, Gautham 2026-10-31: Research became the Workbench, whose Recordings tab is the
 * library at ?view=research). Legacy mode IDs map to their current homes. About links
 * to Live Stack (simulated) and the frozen v1 labs.
 */

import { Settings } from 'lucide-react';
import { openSettings } from '../shell/settings_events';
import '../shell/shell.css';
const BASE = import.meta.env.BASE_URL;

export type ModeId = 'learn' | 'play' | 'sandbox' | 'casefiles' | 'compare' | 'research' | 'workbench' | 'about';
export type Evidence = 'MODEL' | 'STACK';

export const MODES: { id: ModeId; label: string; href: string }[] = [
  { id: 'play', label: 'Play', href: '?view=play' },
  { id: 'learn', label: 'Learn', href: '?view=learn' },
  { id: 'compare', label: 'Compare', href: '?view=compare' },
  { id: 'workbench', label: 'Workbench', href: '?view=workbench' },
];

/** What each class means, said where the badge is (README §3). */
export const EVIDENCE_MEANING: Record<Evidence, string> = {
  MODEL: 'A model in your browser: coco_lab, not the robot and not Gazebo',
  STACK: 'Recorded from the full ROS 2 stack in Gazebo (simulation); no physical robot exists',
};

export function EvidenceBadge({ evidence }: { evidence: Evidence }) {
  return (
    <span className={`evidence-badge ${evidence.toLowerCase()}`} data-testid="evidence-badge" title={EVIDENCE_MEANING[evidence]}>
      {evidence}{evidence === 'MODEL' && ' · kinematic'}
    </span>
  );
}

export function ModeNav({ current, evidence }: { current: ModeId; evidence: Evidence }) {
  const mode = current === 'sandbox' ? 'play' : current === 'casefiles' || current === 'research' ? 'workbench' : current;
  return (
    <header className="mode-head" data-testid="mode-head">
      <a className="brand" href={BASE}>COCO Lab</a>
      <nav className="modes" aria-label="Modes">
        {MODES.map((m) => (
          <a key={m.id} href={`${BASE}${m.href}`} data-testid={`mode-${m.id}`}
            aria-current={m.id === mode ? 'page' : undefined}>{m.label}</a>
        ))}
      </nav>
      <EvidenceBadge evidence={evidence} />
      <button className="settings-gear" aria-label="Settings" onClick={openSettings}><Settings size={20}/></button>
    </header>
  );
}
