// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useRef, useState } from 'react';

import { BundleError } from '../bundle/errors';
import type { Catalog } from '../bundle/load';
import { loadBundleBytes } from '../bundle/load';
import type { RecomputeSpec, WorkerTimings } from '../worker/protocol';
import { requestRecompute, workerStarted } from '../worker/client';
import type { Current } from './App';
import { perfMark } from './perf';

export type LabStatus =
  | { state: 'idle' }
  | { state: 'busy'; message: string }
  | { state: 'done'; message: string; timings: WorkerTimings }
  | { state: 'error'; message: string; refused: boolean };

export interface LabResult {
  bundles: Current[];
  optimalCost: number | null;
}

/**
 * Every change a learner makes -- a brush stroke, new settings, a race --
 * is one request to coco_lab in the Pyodide worker. The page never
 * searches: it sends the CURRENT bundle's bytes and the change, and draws
 * the bundles coco_lab returns, decoded by the same TypeScript decoder as
 * every other bundle.
 */
export function useLab(catalog: Catalog | null) {
  const [status, setStatus] = useState<LabStatus>({ state: 'idle' });
  const busy = useRef(false);

  const run = useCallback(async (current: Current, spec: RecomputeSpec, what: string): Promise<LabResult | null> => {
    if (busy.current || !catalog?.wheel) return null;
    busy.current = true;
    perfMark('edit-click');
    setStatus({
      state: 'busy',
      message: workerStarted() ? `coco_lab is ${what} in your browser…`
        : `Loading Python (Pyodide ${__PYODIDE_VERSION__}) and coco_lab — the first change takes a while…`,
    });
    try {
      const wheelUrl = new URL(`${import.meta.env.BASE_URL}generated/${catalog.wheel.path}`, window.location.href).href;
      const r = await requestRecompute({
        manifest: current.files.manifest, arraysName: current.files.arraysName,
        arraysFile: current.files.arraysFile, spec, wheelUrl, wheelSha256: catalog.wheel.sha256,
      });
      if (!r.ok) {
        setStatus({
          state: 'error', refused: r.refused,
          message: r.stage === 'load' ? `Could not start coco_lab in the browser: ${r.error}`
            : r.refused ? `Not applied: ${r.error}` : `coco_lab refused this change: ${r.error}`,
        });
        return null;
      }
      const bundles: Current[] = [];
      for (const w of r.bundles) {
        const bundle = await loadBundleBytes(w.manifest, w.arraysFile);
        if (bundle.contentHash !== w.contentHash) {
          throw new BundleError('hash', `the worker's bundle hash ${w.contentHash} is not what the decoder computed`);
        }
        bundles.push({
          entry: current.entry ? { ...current.entry, editable: true } : null,
          bundle,
          files: { manifest: w.manifest, arraysName: w.arraysName, arraysFile: w.arraysFile },
          validated: {
            by: 'pyodide',
            detail: `coco_lab ${r.cocoLabVersion} on Python ${r.pythonVersion} (Pyodide ${r.pyodideVersion}): ` +
              'load_bundle, search, and the bundle serialised and validated by coco_lab',
          },
        });
      }
      perfMark('edit-decoded');
      setStatus({ state: 'done', message: `Done: ${what}.`, timings: r.timings });
      return { bundles, optimalCost: r.optimalCost };
    } catch (exc) {
      setStatus({ state: 'error', refused: false, message: exc instanceof Error ? exc.message : String(exc) });
      return null;
    } finally {
      busy.current = false;
    }
  }, [catalog]);

  return { status, setStatus, run };
}

export function LabStatusLine({ status }: { status: LabStatus }) {
  if (status.state === 'idle') return null;
  return (
    <p className={`edit-status ${status.state}`} data-testid="edit-status" role="status">
      {status.message}
      {status.state === 'done' && (
        <span className="timings">
          {' '}coco_lab: {status.timings.runs} search{status.timings.runs === 1 ? '' : 'es'} {status.timings.search_ms.toFixed(0)} ms,
          load {status.timings.load_bundle_ms.toFixed(0)} ms, write {status.timings.write_bundle_ms.toFixed(0)} ms
          {status.timings.optimal_ms > 0 && `, optimum ${status.timings.optimal_ms.toFixed(0)} ms`}
          {status.timings.pyodide_load_ms !== undefined &&
            ` · first start: Pyodide ${status.timings.pyodide_load_ms.toFixed(0)} ms, install ${(status.timings.wheel_install_ms ?? 0).toFixed(0)} ms`}
        </span>
      )}
    </p>
  );
}
