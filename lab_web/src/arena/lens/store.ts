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

/**
 * Channels filed a second time by one scalar (M3.3): each estimator's own
 * batches, so "the latest estimate of estimator E at or before tick T" is a
 * binary search, not a walk back through every other estimator's batches.
 */
export const INDEXED_SCALAR: Readonly<Record<string, string>> = { 'coco.estimate.pose.v1': 'estimator' };

/** The last batch in tick-ordered `list` with tick <= `tick`. */
function lastAtOrBefore(list: FamilyBatch[] | undefined, tick: number): FamilyBatch | null {
  if (!list || list.length === 0 || list[0].tick > tick) return null;
  let lo = 0;
  let hi = list.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (list[mid].tick <= tick) lo = mid; else hi = mid - 1;
  }
  return list[lo];
}

/** Keep at most this many batches per channel (oldest dropped first). */
export const MAX_BATCHES_PER_CHANNEL = 20_000;

export class FamilyStore {
  private byChannel = new Map<string, FamilyBatch[]>();
  private metrics = new Map<string, MetricPoint[]>();
  private byScalar = new Map<string, Map<string, FamilyBatch[]>>();
  /** Bumped on every add: renderers redraw only when it changed. */
  version = 0;

  add(b: FamilyBatch) {
    let list = this.byChannel.get(b.channel);
    if (!list) { list = []; this.byChannel.set(b.channel, list); }
    // batches arrive in tick order; a recording may repeat a tick (several batches per tick)
    list.push(b);
    if (list.length > MAX_BATCHES_PER_CHANNEL) list.splice(0, list.length - MAX_BATCHES_PER_CHANNEL);
    const key = INDEXED_SCALAR[b.channel];
    if (key !== undefined && b.scalars[key] !== undefined) {
      let by = this.byScalar.get(b.channel);
      if (!by) { by = new Map(); this.byScalar.set(b.channel, by); }
      const v = String(b.scalars[key]);
      let own = by.get(v);
      if (!own) { own = []; by.set(v, own); }
      own.push(b);
      if (own.length > MAX_BATCHES_PER_CHANNEL) own.splice(0, own.length - MAX_BATCHES_PER_CHANNEL);
    }
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
    return lastAtOrBefore(this.byChannel.get(channel), tick);
  }

  /** The last batch of `channel` whose indexed scalar equals `value`, at or before `tick` (INDEXED_SCALAR). */
  latestWhere(channel: string, value: string, tick: number): FamilyBatch | null {
    return lastAtOrBefore(this.byScalar.get(channel)?.get(value), tick);
  }

  /** Every batch of `channel` whose indexed scalar equals `value`, at or before `tick`, oldest first. */
  beforeWhere(channel: string, value: string, tick: number): FamilyBatch[] {
    const own = this.byScalar.get(channel)?.get(value);
    if (!own) return [];
    const last = lastAtOrBefore(own, tick);
    return last ? own.slice(0, own.lastIndexOf(last) + 1) : [];
  }

  /** The values the indexed scalar of `channel` has taken (e.g. every estimator seen), in first-seen order. */
  scalarValues(channel: string): string[] {
    return [...(this.byScalar.get(channel)?.keys() ?? [])];
  }

  /** Every batch of `channel` with tick <= `tick`, oldest first (a trajectory). */
  before(channel: string, tick: number): FamilyBatch[] {
    const list = this.byChannel.get(channel) ?? [];
    let n = list.length;
    while (n > 0 && list[n - 1].tick > tick) n -= 1;
    return list.slice(0, n);
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
    this.byScalar.clear();
    this.version += 1;
  }
}

/** The family a channel belongs to (coco.<family>.<name>.v<major>; families may have two parts). */
export function familyOf(channel: string): string {
  const body = channel.replace(/^coco\./, '').replace(/\.v\d+$/, '');
  const parts = body.split('.');
  return parts.slice(0, -1).join('.');
}
