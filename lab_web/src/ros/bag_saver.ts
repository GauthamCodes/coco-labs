// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.5: "Save as rosbag2 (MCAP)" from the pause menu and the results screen. Play registers
 * how to write its run (src/ros/bag.ts); the menu asks for the file and the browser downloads
 * it. Nothing is uploaded or stored: the file goes straight to the person's downloads.
 */

export interface BagFile { name: string; bytes: Uint8Array }

let source: (() => Promise<BagFile>) | null = null;

export function registerBagSource(fn: () => Promise<BagFile>): () => void {
  source = fn;
  return () => { if (source === fn) source = null; };
}

export const hasBagSource = () => source !== null;

/** Write and download the run's bag; returns its name and size, or why it could not. */
export async function saveBag(): Promise<{ ok: true; name: string; bytes: number } | { ok: false; why: string }> {
  if (!source) return { ok: false, why: 'no run to save' };
  try {
    const f = await source();
    const url = URL.createObjectURL(new Blob([f.bytes.slice().buffer as ArrayBuffer], { type: 'application/octet-stream' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = f.name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
    return { ok: true, name: f.name, bytes: f.bytes.length };
  } catch (e) {
    return { ok: false, why: String((e as Error).message ?? e) };
  }
}

/** coco_lab_<game>_<mode>_seed<N>_<YYYYMMDD-HHMMSS>.mcap (local time of saving) */
export function bagName(game: string, mode: string | undefined, seed: number, at = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0');
  const stamp = `${at.getFullYear()}${p(at.getMonth() + 1)}${p(at.getDate())}-${p(at.getHours())}${p(at.getMinutes())}${p(at.getSeconds())}`;
  return `coco_lab_${game}${mode ? `_${mode}` : ''}_seed${seed}_${stamp}.mcap`;
}
