// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * What the lenses read (M2.2): every family batch the model emitted, kept
 * per channel in tick order, so the timeline can show any tick's state. A
 * batch arrives from the worker as columns (ADR 0001: numeric columns as
 * transferred typed arrays, strings and bools as plain arrays) plus its
 * per-batch scalars. Nothing here computes an algorithm: it files batches
 * and answers "the latest batch of channel C at or before tick T" and "the
 * series of metric M up to tick T".
 */

export type FamilyColumn = ArrayLike<number> | ArrayLike<bigint> | boolean[] | string[];

export interface FamilyBatch {
  channel: string;
  /** The tick it belongs to (the model's tick when it was emitted). */
  tick: number;
  columns: Record<string, FamilyColumn>;
  scalars: Record<string, number | string | boolean>;
}

export interface MetricPoint { tick: number; value: number }

/** Keep at most this many batches per channel (oldest dropped first). */
export const MAX_BATCHES_PER_CHANNEL = 20_000;

export class FamilyStore {
  private byChannel = new Map<string, FamilyBatch[]>();
  private metrics = new Map<string, MetricPoint[]>();
  /** Bumped on every add: renderers redraw only when it changed. */
  version = 0;

  add(b: FamilyBatch) {
    let list = this.byChannel.get(b.channel);
    if (!list) { list = []; this.byChannel.set(b.channel, list); }
    // batches arrive in tick order; a recording may repeat a tick (several batches per tick)
    list.push(b);
    if (list.length > MAX_BATCHES_PER_CHANNEL) list.splice(0, list.length - MAX_BATCHES_PER_CHANNEL);
    if (b.channel === 'coco.metrics.values.v1') {
      const names = b.columns.name as string[];
      const values = b.columns.value as ArrayLike<number>;
      const ticks = b.columns.tick as ArrayLike<bigint | number>;
      for (let i = 0; i < names.length; i += 1) {
        let s = this.metrics.get(names[i]);
        if (!s) { s = []; this.metrics.set(names[i], s); }
        s.push({ tick: Number(ticks[i]), value: values[i] });
      }
    }
    this.version += 1;
  }

  channels(): string[] {
    return [...this.byChannel.keys()];
  }

  /** The last batch of `channel` with tick <= `tick` (all batches of that tick: the last one). */
  latest(channel: string, tick: number): FamilyBatch | null {
    const list = this.byChannel.get(channel);
    if (!list || list.length === 0) return null;
    let lo = 0;
    let hi = list.length - 1;
    if (list[0].tick > tick) return null;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (list[mid].tick <= tick) lo = mid; else hi = mid - 1;
    }
    return list[lo];
  }

  /** Every batch of `channel` at exactly `tick`, in arrival order. */
  at(channel: string, tick: number): FamilyBatch[] {
    return (this.byChannel.get(channel) ?? []).filter((b) => b.tick === tick);
  }

  /** The last `n` batches of the given channels at or before `tick`, newest last (the event log). */
  recent(channels: readonly string[], tick: number, n: number): FamilyBatch[] {
    const out: FamilyBatch[] = [];
    for (const c of channels) {
      const list = this.byChannel.get(c) ?? [];
      for (let i = list.length - 1; i >= 0 && out.length < n * channels.length; i -= 1) {
        if (list[i].tick <= tick) out.push(list[i]);
        if (list[i].tick <= tick - 2000) break;
      }
    }
    return out.sort((a, b) => a.tick - b.tick).slice(-n);
  }

  /** A metric's values up to `tick` (for an Inspect chart). */
  series(name: string, tick: number): MetricPoint[] {
    return (this.metrics.get(name) ?? []).filter((p) => p.tick <= tick);
  }

  metricNames(): string[] {
    return [...this.metrics.keys()];
  }

  clear() {
    this.byChannel.clear();
    this.metrics.clear();
    this.version += 1;
  }
}

/** The family a channel belongs to (coco.<family>.<name>.v<major>; families may have two parts). */
export function familyOf(channel: string): string {
  const body = channel.replace(/^coco\./, '').replace(/\.v\d+$/, '');
  const parts = body.split('.');
  return parts.slice(0, -1).join('.');
}
