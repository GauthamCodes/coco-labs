// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useRef, useState } from 'react';

import { BundleError } from '../bundle/errors';
import type { Catalog } from '../bundle/load';
import { loadBundleBytes } from '../bundle/load';
import type { WorkerTimings } from '../worker/protocol';
import { requestEdit, workerStarted } from '../worker/client';
import type { Current } from './App';
import { perfMark } from './perf';

export type EditStatus =
  | { state: 'idle' }
  | { state: 'busy'; message: string }
  | { state: 'done'; message: string; timings: WorkerTimings }
  | { state: 'error'; message: string };

/**
 * Minimal edit (Phase 1D): click a cell to toggle it free/occupied; coco_lab
 * reruns the SAME run inputs in the Pyodide worker. Desktop-first; the full
 * painting UX is Phase 1E.
 */
export function useEditor(catalog: Catalog | null, show: (c: Current) => void) {
  const [status, setStatus] = useState<EditStatus>({ state: 'idle' });
  const busy = useRef(false);

  const edit = useCallback(async (current: Current, cell: [number, number]) => {
    if (busy.current || !catalog?.wheel) return;
    busy.current = true;
    perfMark('edit-click');
    setStatus({
      state: 'busy',
      message: workerStarted() ? 'coco_lab is recomputing in your browser…'
        : `Loading Python (Pyodide ${__PYODIDE_VERSION__}) and coco_lab — the first edit takes a while…`,
    });
    try {
      const wheelUrl = new URL(`${import.meta.env.BASE_URL}generated/${catalog.wheel.path}`, window.location.href).href;
      const r = await requestEdit({
        manifest: current.files.manifest, arraysName: current.files.arraysName,
        arraysFile: current.files.arraysFile, cell, wheelUrl, wheelSha256: catalog.wheel.sha256,
      });
      if (!r.ok) {
        setStatus({
          state: 'error',
          message: r.stage === 'load' ? `Could not start coco_lab in the browser: ${r.error}`
            : `coco_lab refused this edit: ${r.error}`,
        });
        return;
      }
      const bundle = await loadBundleBytes(r.manifest, r.arraysFile);
      if (bundle.contentHash !== r.contentHash) {
        throw new BundleError('hash', `the worker's bundle hash ${r.contentHash} is not what the decoder computed`);
      }
      perfMark('edit-decoded');
      show({
        entry: current.entry ? { ...current.entry, editable: true } : null,
        bundle,
        files: { manifest: r.manifest, arraysName: r.arraysName, arraysFile: r.arraysFile },
        validated: {
          by: 'pyodide',
          detail: `coco_lab ${r.cocoLabVersion} on Python ${r.pythonVersion} (Pyodide ${r.pyodideVersion}): ` +
            'load_bundle, search, write_bundle (which validates)',
        },
      });
      setStatus({ state: 'done', message: `Toggled cell [${cell[0]}, ${cell[1]}] and recomputed.`, timings: r.timings });
    } catch (exc) {
      setStatus({ state: 'error', message: exc instanceof Error ? exc.message : String(exc) });
    } finally {
      busy.current = false;
    }
  }, [catalog, show]);

  return { status, setStatus, edit };
}

export function Editor({ editable, status }: { editable: boolean; status: EditStatus }) {
  if (!editable) {
    return <p className="edit-note">Recorded runs are shown as recorded; they are not editable.</p>;
  }
  return (
    <div className="editor" data-testid="editor">
      <p className="edit-note">
        Desktop: click a cell to toggle it free/occupied. coco_lab reruns the same algorithm, heuristic,
        start and goal <em>in your browser</em> (Python via Pyodide) — the page never searches itself.
      </p>
      {status.state !== 'idle' && (
        <p className={`edit-status ${status.state}`} data-testid="edit-status" role="status">
          {status.message}
          {status.state === 'done' && (
            <span className="timings">
              {' '}coco_lab: search {status.timings.search_ms.toFixed(0)} ms, load {status.timings.load_bundle_ms.toFixed(0)} ms,
              write {status.timings.write_bundle_ms.toFixed(0)} ms
              {status.timings.pyodide_load_ms !== undefined &&
                ` · first start: Pyodide ${status.timings.pyodide_load_ms.toFixed(0)} ms, install ${(status.timings.wheel_install_ms ?? 0).toFixed(0)} ms`}
            </span>
          )}
        </p>
      )}
    </div>
  );
}
