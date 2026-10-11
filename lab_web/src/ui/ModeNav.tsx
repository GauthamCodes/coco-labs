// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * One app, four modes (M3.7): Learn · Play · Sandbox · Case Files, the same
 * header in each, with the evidence badge for what is on screen (README §3's
 * classes). The Live Stack (simulated) view stays reachable here but is not
 * a mode; the frozen v1 labs likewise.
 */

const BASE = import.meta.env.BASE_URL;

export type ModeId = 'learn' | 'play' | 'sandbox' | 'casefiles';
export type Evidence = 'MODEL' | 'STACK';

export const MODES: { id: ModeId; label: string; href: string }[] = [
  { id: 'learn', label: 'Learn', href: '?view=learn' },
  { id: 'play', label: 'Play', href: '?view=play' },
  { id: 'sandbox', label: 'Sandbox', href: '?view=arena' },
  { id: 'casefiles', label: 'Case Files', href: '?view=casefiles' },
];

/** What each class means, said where the badge is (README §3). */
export const EVIDENCE_MEANING: Record<Evidence, string> = {
  MODEL: 'A model in your browser: coco_lab, not the robot and not Gazebo',
  STACK: 'Recorded from the full ROS 2 stack in Gazebo (simulation); no physical robot exists',
};

export function EvidenceBadge({ evidence }: { evidence: Evidence }) {
  return (
    <span className={`evidence-badge ${evidence.toLowerCase()}`} data-testid="evidence-badge" title={EVIDENCE_MEANING[evidence]}>
      {evidence}
    </span>
  );
}

export function ModeNav({ current, evidence }: { current: ModeId; evidence: Evidence }) {
  return (
    <header className="mode-head" data-testid="mode-head">
      <a className="brand" href={`${BASE}?view=arena`}>COCO Lab</a>
      <nav className="modes" aria-label="Modes">
        {MODES.map((m) => (
          <a key={m.id} href={`${BASE}${m.href}`} data-testid={`mode-${m.id}`}
            aria-current={m.id === current ? 'page' : undefined}>{m.label}</a>
        ))}
      </nav>
      <EvidenceBadge evidence={evidence} />
      <span className="mode-aside">
        <a href={`${BASE}?view=live`} data-testid="live-link">Live Stack (simulated)</a>
        {' · '}
        <a href={`${BASE}v1/`} data-testid="v1-labs-link">v1 labs (archive)</a>
      </span>
    </header>
  );
}
