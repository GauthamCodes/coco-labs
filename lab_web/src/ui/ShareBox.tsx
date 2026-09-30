// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useState } from 'react';

export interface ShareBoxProps {
  /** Builds the link for what is on screen now. */
  makeLink: () => Promise<string>;
  /** After opening a link: whether coco_lab reproduced its trace. */
  verdict: { ok: boolean | null; message: string } | null;
}

/**
 * Share this view: a link that names the bundle, the settings and your map
 * edits (src/lab/share.ts). Whoever opens it reruns coco_lab on the same
 * inputs; the link carries the trace's digest, so the page can say whether
 * the trace came out identical.
 */
export function ShareBox({ makeLink, verdict }: ShareBoxProps) {
  const [link, setLink] = useState<string | null>(null);
  const [note, setNote] = useState('');
  return (
    <div className="share" data-testid="share">
      {verdict && (
        <p className={`share-verdict ${verdict.ok === false ? 'bad' : ''}`} data-testid="share-verdict" role="status">
          {verdict.message}
        </p>
      )}
      <button type="button" className="seg-btn" data-testid="share-make" onClick={async () => {
        try {
          const l = await makeLink();
          setLink(l);
          setNote('');
          try {
            await navigator.clipboard.writeText(l);
            setNote('Copied.');
          } catch {
            setNote('Select the link to copy it.');
          }
        } catch (exc) {
          setLink(null);
          setNote(`Cannot share this view: ${exc instanceof Error ? exc.message : String(exc)}`);
        }
      }}>Share this view</button>
      {link && (
        <input className="share-link" readOnly value={link} data-testid="share-link" aria-label="Share link"
          onFocus={(e) => e.currentTarget.select()} />
      )}
      {note && <span className="note">{note}</span>}
    </div>
  );
}
