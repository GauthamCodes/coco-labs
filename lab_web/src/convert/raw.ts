// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The shared half of every v1 -> v2 converter's way back (M2.7): rebuild a
 * coco_lab bundle's raw array bytes from columns taken off the v2
 * channels, in the order and the dtypes the bundle's own manifest lists.
 * A converter then hands those bytes to the lab's own decoder, which
 * re-checks the content hash -- so "lossless" is "decodes".
 */

import { JInt, isObj, type JNode, type JObject } from '../bundle/json';

/** Write every array the manifest lists from `col`; refuse a missing or mis-sized one. */
export function rawFromColumns(tree: JObject, total: number, col: Record<string, ArrayLike<number>>): Uint8Array {
  const table = (tree.get('arrays') as JNode[]).filter(isObj);
  const raw = new Uint8Array(total);
  const dv = new DataView(raw.buffer);
  for (const a of table) {
    const name = a.get('name') as string;
    const dtype = a.get('dtype') as string;
    const count = (a.get('count') as JInt).value;
    let off = (a.get('offset') as JInt).value;
    const v = col[name] ?? (count === 0 ? [] : undefined);
    if (!v) throw new Error(`no v2 channel carries ${name}`);
    if (v.length !== count) throw new Error(`${name}: ${v.length} values from the channels, the bundle has ${count}`);
    for (let i = 0; i < count; i += 1) {
      if (dtype === 'u8') { dv.setUint8(off, v[i]); off += 1; } else if (dtype === 'i32') { dv.setInt32(off, v[i], true); off += 4; } else if (dtype === 'f32') {
        dv.setFloat32(off, v[i], true); off += 4;
      } else if (dtype === 'f64') { dv.setFloat64(off, v[i], true); off += 8; } else throw new Error(`${name}: dtype ${dtype}`);
    }
  }
  return raw;
}

/** The array names a manifest lists. */
export function arrayNames(tree: JObject): string[] {
  return (tree.get('arrays') as JNode[]).filter(isObj).map((a) => a.get('name') as string);
}

/** Row counters per (channel, key), so seq runs on across batches as coco_lab.columns.Batch does. */
export class Seq {
  private next = new Map<string, number>();

  take(channel: string, key: string, n: number): bigint[] {
    const k = `${channel}|${key}`;
    const s = this.next.get(k) ?? 0;
    this.next.set(k, s + n);
    return Array.from({ length: n }, (_, i) => BigInt(s + i));
  }
}
