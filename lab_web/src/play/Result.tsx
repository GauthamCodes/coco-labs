// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {trapDialogTab} from '../ui/dialog';

/** A Play score on screen (M3.5): the stars, every named metric, the thresholds, the link. */

import { useEffect, useState, useRef, type ReactNode } from 'react';

import { evidenceHref } from '../learn/LearnApp';
import { keepBest, type Best, type PlayResult } from './best';
import { encodeScore, type Submission } from './share';

const BASE = import.meta.env.BASE_URL;

export const stars = (n: number) => '★'.repeat(n) + '☆'.repeat(3 - n);

function show(v: unknown): string {
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(4);
  if (typeof v === 'boolean') return v ? 'yes' : 'no';
  if (Array.isArray(v)) return v.map((x) => (x === true ? '✓' : x === false ? '✗' : String(x))).join(' ');
  return v === null || v === undefined ? '—' : String(v);
}

export function ResultView({ result, submission, reproduced, onReplay, pathReview }: {
  result: PlayResult; submission: Submission; reproduced?: boolean | null; onReplay?:()=>void; pathReview?:ReactNode;
}) {
  const dialog=useRef<HTMLDialogElement>(null);
  const heading=useRef<HTMLHeadingElement>(null);
  const [review,setReview]=useState(false);
  useEffect(()=>{if(dialog.current&&!dialog.current.open){dialog.current.showModal();heading.current?.focus({preventScroll:true});dialog.current.scrollTop=0;}},[result]);
  const replay=()=>{dialog.current?.close();setReview(true);onReplay?.();};
  const retry=()=>{
    const query=new URLSearchParams(window.location.search);query.delete('s');query.delete('z');
    window.location.assign(`${window.location.pathname}?${query}`);
  };
  const [best, setBest] = useState<Best | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => { if (reproduced === undefined) setBest(keepBest(result)); }, [result, reproduced]);
  const link = `${window.location.origin}${BASE}${encodeScore({ submission, result_hash: result.hash })}`;
  const copy = () => {
    void navigator.clipboard?.writeText(link).then(() => setCopied(true)).catch(() => setCopied(false));
  };
  return (
    <><button className="score-return" hidden={!review} onClick={()=>{setReview(false);dialog.current?.showModal();heading.current?.focus({preventScroll:true});if(dialog.current)dialog.current.scrollTop=0;}}>Back to scorecard</button>
    <dialog className="play-scorecard" onKeyDown={trapDialogTab} ref={dialog} aria-label="Scorecard" onCancel={()=>setReview(true)}>
    <section className="play-result" data-testid="play-result" data-hash={result.hash} data-stars={result.stars}
      data-valid={String(result.valid)}>
      <header><h1 ref={heading} tabIndex={-1}>{result.valid?'Your result':'Run not scored'}</h1><span>MODEL · kinematic</span></header>
      {pathReview}
      {reproduced !== undefined && reproduced !== null && (
        <p className={reproduced ? 'reproduced' : 'not-reproduced'} data-testid="play-reproduced" role="status">
          {reproduced ? 'Reproduced exactly: re-scored from the link\'s inputs, the same result hash.'
            : 'Did NOT reproduce: re-scored from the link\'s inputs, the result hash differs.'}</p>
      )}
      {!result.valid && <p className="play-invalid" data-testid="play-why">Not scored: {result.why}</p>}
      <p className="play-stars" aria-label={`${result.stars} of 3 stars`}>{stars(result.stars)}{' '}
        <span className="play-score">{result.score.name}: <b data-testid="play-score">{show(result.score.value)}</b></span></p>
      <table className="play-metrics">
        <tbody>
          {result.metrics.map((m) => (
            <tr key={m.name} data-metric={m.name}>
              <th>{m.name.replace(/_/g, ' ')}</th>
              <td>{show(m.value)}{m.unit ? ` ${m.unit}` : ''}</td>
              <td className="meaning">{m.meaning}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <ol className="play-thresholds">
        {result.thresholds.map((t, i) => <li key={t} className={i < result.stars ? 'met' : ''}>{stars(i + 1).replace(/☆/g, '')} {t}</li>)}
      </ol>
      <p className="cite">Stars come from reference algorithms on this level:{' '}
        <a href={evidenceHref('docs/v2/CHALLENGES.md')} target="_blank" rel="noreferrer">docs/v2/CHALLENGES.md</a>.
        Result hash <code>{result.hash.slice(0, 12)}</code>.</p>
      <div className="score-actions"><button onClick={replay}>Replay</button><button onClick={retry}>Try again</button><button onClick={copy}>Share</button></div>
      {reproduced === undefined && (
        <p className="play-share">
          <button type="button" onClick={copy} data-testid="play-copy">Copy a challenge link</button>{' '}
          <a href={link} data-testid="play-link">{copied ? 'copied' : 'the link'}</a>
          {best && <span className="play-best" data-testid="play-best"> · your best here: {stars(best.stars)} {show(best.score)}</span>}
        </p>
      )}
    </section></dialog></>
  );
}
