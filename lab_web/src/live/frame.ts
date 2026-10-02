// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * coco.v1 binary frames, decoded by coco_web's OWN `web/frame.js`.
 *
 * Not a port. The build copies that file, byte for byte, to
 * `<base>coco/frame.js` (vite.config.ts; `tools/check_dist.mjs` checks the
 * copy is identical), and the Live tab loads it as a classic script, which
 * the CSP's `script-src 'self'` already allows. The vitest suite loads the
 * same source file with `require` and decodes the fixtures coco_web
 * commits (`coco_web/test/fixtures/frames.json`). One decoder, one fixture
 * set, two test suites.
 */

export interface DecodedFrame {
  stream: 'lidar' | 'camera' | 'depth';
  header: Record<string, unknown> & { seq: number; t: number; dropped: number };
  payload: ArrayBuffer;
  ranges?: (number | null)[];
}

interface CocoFrameApi { decodeFrame(buf: ArrayBuffer): DecodedFrame }

declare global {
  // Set by coco_web/web/frame.js when loaded as a classic script.
  var cocoFrame: CocoFrameApi | undefined;
}

let loading: Promise<void> | null = null;

/** Load coco_web's decoder once, from this site's own origin. */
export function loadFrameDecoder(base: string): Promise<void> {
  if (globalThis.cocoFrame) return Promise.resolve();
  loading ??= new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = `${base}coco/frame.js`;
    s.onload = () => (globalThis.cocoFrame ? resolve() : reject(new Error('frame.js did not define cocoFrame')));
    s.onerror = () => reject(new Error(`could not load ${s.src}`));
    document.head.appendChild(s);
  });
  return loading;
}

/** Decode one binary frame; throws (with the decoder's reason) if refused. */
export function decodeFrame(buf: ArrayBuffer): DecodedFrame {
  const api = globalThis.cocoFrame;
  if (!api) throw new Error('frame decoder not loaded');
  return api.decodeFrame(buf);
}
