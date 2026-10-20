// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** G1.8: "New version ready" -- Save run and Reload, both the player's choice; never an automatic reload. */
import { useEffect, useState } from 'react';
import { hasRunSaver, onUpdate, saveRun, updateReady } from '../offline/updates';

export function UpdateNotice() {
  const [ready, setReady] = useState(updateReady());
  const [saved, setSaved] = useState<'idle' | 'saved' | 'none'>('idle');
  useEffect(() => onUpdate(() => setReady(updateReady())), []);
  if (!ready) return null;
  return <div className="update-notice" role="status" data-testid="update-notice">
    <span>New version ready</span>
    <button type="button" data-testid="update-save" onClick={() => { void saveRun().then((ok) => setSaved(ok ? 'saved' : 'none')); }}
      disabled={!hasRunSaver()} title={hasRunSaver() ? 'Download this run (its input log) before reloading' : 'No run in progress'}>
      {saved === 'saved' ? 'Saved' : 'Save run'}</button>
    <button type="button" data-testid="update-reload" onClick={() => window.location.reload()}>Reload</button>
  </div>;
}
