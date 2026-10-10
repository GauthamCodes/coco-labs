// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Case Files (M3.3): every recorded full-stack run, inspectable.
 *
 *   ?view=casefiles                      the groups
 *   ?view=casefiles&case=<group>         one group: what was recorded, what it showed, what is unresolved
 *   ?view=casefiles&case=<group>&file=<id>  one recording beside the Arena model on the same scenario
 *
 * The text is generated/casefiles/cases.json (lab_web/tools/casefiles.py:
 * every sentence carries its learner label and evidence that resolves, or
 * the build fails). A recording is STACK -- the full ROS 2 stack in Gazebo,
 * no physical robot -- and the model beside it is MODEL; each pane says so.
 */

import { useEffect, useState } from 'react';

import { GapChips, useGaps } from '../learn/gaps';
import { evidenceHref, LABEL_MEANING } from '../learn/LearnApp';

const BASE = import.meta.env.BASE_URL;

interface Sentence { label: string; text: string; resolved: string[] }
interface CaseFile {
  id: string; title: string; file: string; bytes: number; sha256: string; run_id: string; bags: string[];
  checksum: { checked: boolean; definition?: string; sha256?: string; cited_in?: string; why?: string };
  void: boolean; facts: { label: string; text: string; evidence: string[] }[]; compare: string;
}
interface Group {
  id: string; title: string; lab: number; gaps: string[]; results: string[]; results_resolved: string[];
  explain: Sentence[]; unresolved: Sentence[]; compare: { what: string; url: string };
  casefiles: CaseFile[]; members?: string[]; backends?: Record<string, unknown>[];
}
interface Doc { groups: Group[]; total_bytes: number }

function Claim({ s, testid }: { s: Sentence; testid: string }) {
  return (
    <div className="claim" data-testid={testid}>
      <span className={`claim-label ${s.label.toLowerCase().replace(/\s+/g, '-')}`} title={LABEL_MEANING[s.label]}>{s.label}</span>
      <p>{s.text}</p>
      <p className="cite">Evidence:{' '}
        {s.resolved.map((r, i) => (
          <span key={r}>{i > 0 && '; '}<a href={evidenceHref(r)} target="_blank" rel="noreferrer">{r}</a></span>
        ))}
      </p>
    </div>
  );
}

const kb = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${Math.round(n / 1e3)} KB`);

export function CaseFilesApp() {
  const params = new URLSearchParams(window.location.search);
  const caseId = params.get('case');
  const fileId = params.get('file');
  const [doc, setDoc] = useState<Doc | null>(null);
  const [error, setError] = useState<string | null>(null);
  const gaps = useGaps(BASE);
  useEffect(() => {
    void fetch(`${BASE}generated/casefiles/cases.json`, { credentials: 'omit' })
      .then((r) => { if (!r.ok) throw new Error('no Case Files in this build'); return r.json(); })
      .then(setDoc).catch((e) => setError((e as Error).message));
  }, []);
  if (error) return <main className="casefiles"><p className="error" role="alert">{error}</p></main>;
  if (!doc) return <main className="casefiles"><p>Loading the Case Files…</p></main>;
  const group = caseId ? doc.groups.find((g) => g.id === caseId) : undefined;
  if (caseId && !group) return <main className="casefiles"><p className="error" role="alert">No Case File "{caseId}".</p></main>;
  const all = new Map(doc.groups.flatMap((g) => g.casefiles.map((c) => [c.id, { c, g }] as const)));

  if (!group) {
    return (
      <main className="casefiles" data-testid="casefiles">
        <header className="casefiles-head">
          <h1>Case Files</h1>
          <span className="evidence-badge stack" data-testid="evidence-badge">STACK</span>
        </header>
        <p className="note">Every run recorded on the full ROS 2 stack in Gazebo, failures included, inspectable in the
          same viewer as the Arena model. No physical robot exists: these are simulation results. {all.size} recordings,{' '}
          {kb(doc.total_bytes)}, each fetched only when opened.</p>
        <ul className="casefile-groups">
          {doc.groups.map((g) => (
            <li key={g.id} data-testid={`group-${g.id}`}>
              <a href={`${BASE}?view=casefiles&case=${g.id}`}>{g.title}</a>
              <span className="note"> · {g.casefiles.length || g.members?.length || 0} recordings</span>
            </li>
          ))}
        </ul>
      </main>
    );
  }

  const file = fileId ? group.casefiles.find((c) => c.id === fileId) ?? all.get(fileId)?.c : undefined;
  const members = (group.members ?? []).map((id) => all.get(id)).filter(Boolean) as { c: CaseFile; g: Group }[];
  return (
    <main className="casefiles" data-testid="casefile-group" data-group={group.id}>
      <nav className="casefiles-nav"><a href={`${BASE}?view=casefiles`}>← Case Files</a></nav>
      <header className="casefiles-head">
        <h1>{group.title}</h1>
        <span className="evidence-badge stack" data-testid="evidence-badge">STACK</span>
      </header>
      {file && (
        <section className="casefile-compare" data-testid="casefile-compare" data-file={file.id}>
          <h2>{file.title}{file.void && ' — VOID, not counted'}</h2>
          <div className="compare-panes">
            <figure>
              <figcaption><span className="evidence-badge stack">STACK</span> the recording, as the stack ran it</figcaption>
              <iframe title={`recording ${file.id}`} src={`${BASE}?view=arena&casefile=${file.id}`} data-testid="pane-stack" />
            </figure>
            {!file.void && (
              <figure>
                <figcaption><span className="evidence-badge model">MODEL</span> {group.compare.what}</figcaption>
                <iframe title={`model ${file.id}`} src={`${BASE}${file.compare}`} data-testid="pane-model" />
              </figure>
            )}
          </div>
          <GapChips ids={group.gaps} gaps={gaps} />
          {file.facts.map((f, i) => (
            <Claim key={i} s={{ label: f.label, text: f.text, resolved: f.evidence }} testid={`fact-${i}`} />
          ))}
          <p className="cite" data-testid="citation">Recorded in {file.bags.join(' + ')}
            {file.checksum.checked
              ? ` — checked against ${file.checksum.cited_in} (${file.checksum.definition}: ${file.checksum.sha256?.slice(0, 12)}…)`
              : ` — every source file cited by sha256 in the Case File's own manifest (${file.checksum.why ?? 'no committed citation'})`}.
            {' '}Case File {kb(file.bytes)}, run {file.run_id.slice(0, 12)}…</p>
        </section>
      )}
      <section data-testid="explain">
        <h2>What was recorded, and what it showed</h2>
        {group.explain.map((s, i) => <Claim key={i} s={s} testid={`explain-${i}`} />)}
      </section>
      {group.unresolved.length > 0 && (
        <section data-testid="unresolved">
          <h2>Still unresolved</h2>
          {group.unresolved.map((s, i) => <Claim key={i} s={s} testid={`unresolved-${i}`} />)}
        </section>
      )}
      {!file && <GapChips ids={group.gaps} gaps={gaps} />}
      <section>
        <h2>The recordings</h2>
        <ul className="casefile-list" data-testid="casefile-list">
          {[...group.casefiles.map((c) => ({ c, g: group })), ...members].map(({ c, g }) => (
            <li key={c.id} data-testid={`casefile-${c.id}`}>
              <a href={`${BASE}?view=casefiles&case=${g.id}&file=${c.id}`}>{c.title}</a>
              {c.void && <span className="claim-label unresolved"> VOID</span>}
              <span className="note"> · {c.facts[0]?.text ?? ''} · {kb(c.bytes)}</span>
            </li>
          ))}
        </ul>
      </section>
      {group.backends && group.backends.length > 0 && (
        <section data-testid="backends">
          <h2>The backends' maps, as Lab 3 scored them</h2>
          <table className="casefile-table">
            <thead><tr>{Object.keys(group.backends[0]).map((k) => <th key={k}>{k}</th>)}</tr></thead>
            <tbody>{group.backends.map((b, i) => (
              <tr key={i}>{Object.values(b).map((v, j) => <td key={j}>{String(v)}</td>)}</tr>
            ))}</tbody>
          </table>
        </section>
      )}
      <p className="cite" data-testid="results-links">In docs/RESULTS.md:{' '}
        {group.results_resolved.map((r, i) => <span key={r}>{i > 0 && '; '}<a href={evidenceHref(r)} target="_blank" rel="noreferrer">{r}</a></span>)}
      </p>
    </main>
  );
}
