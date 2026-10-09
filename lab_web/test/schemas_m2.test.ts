// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The whole loop's families (M2.1), across languages: for every M2 `*Batch`
 * message coco_lab declares, the batch Python filled and Python protobuf
 * encoded (coco_schemas/test/vectors/m2_batches.json, written by
 * coco_schemas/scripts/make_vectors_m2.py) must come out of TypeScript's
 * encodeBatch byte for byte, and decode back to the same columns.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fromBinary, type DescMessage } from '@bufbuild/protobuf';
import { describe, expect, it } from 'vitest';

import { encodeBatch, type Column } from '../src/schemas/columns';
import * as arm from '../src/schemas/gen/coco/arm/v1/arm_pb';
import * as control from '../src/schemas/gen/coco/control/v1/control_pb';
import * as decide from '../src/schemas/gen/coco/decide/v1/decide_pb';
import * as estimate from '../src/schemas/gen/coco/estimate/v1/estimate_pb';
import * as localise from '../src/schemas/gen/coco/localise/v1/localise_pb';
import * as map from '../src/schemas/gen/coco/map/v1/map_pb';
import * as mission from '../src/schemas/gen/coco/mission/v1/mission_pb';
import * as detect from '../src/schemas/gen/coco/sensor/v1/detect_pb';
import { REPO } from './helpers';

interface Vec {
  message: string;
  types: Record<string, string>;
  scalar_types: Record<string, string>;
  columns: Record<string, (number | string | boolean)[]>;
  scalars: Record<string, number | string | boolean>;
  protobuf_b64: string;
}

const VECS: Vec[] = JSON.parse(readFileSync(join(REPO, 'coco_schemas', 'test', 'vectors', 'm2_batches.json'), 'utf-8')).vectors;

const DESCS = new Map<string, DescMessage>();
for (const mod of [arm, control, decide, estimate, localise, map, mission, detect] as Record<string, unknown>[]) {
  for (const v of Object.values(mod)) {
    const d = v as DescMessage;
    if (d && typeof d === 'object' && d.kind === 'message') DESCS.set(d.typeName, d);
  }
}

function column(t: string, xs: (number | string | boolean)[]): Column {
  switch (t) {
    case 'Q': return BigUint64Array.from(xs.map((x) => BigInt(x as string)));
    case 'd': return Float64Array.from(xs as number[]);
    case 'f': return Float32Array.from(xs as number[]);
    case 'I': return Uint32Array.from(xs as number[]);
    case 'i': return Int32Array.from(xs as number[]);
    case 'B': return xs as boolean[];
    default: return xs as string[];
  }
}

describe('M2 batches: TypeScript encodes what Python protobuf encodes', () => {
  it('covers every whole-loop batch message', () => {
    expect(VECS.length).toBe(18);
    for (const v of VECS) expect(DESCS.has(v.message), v.message).toBe(true);
  });

  it.each(VECS.map((v) => [v.message, v] as const))('%s', (_, v) => {
    const desc = DESCS.get(v.message)!;
    const cols: Record<string, Column> = {};
    for (const [n, xs] of Object.entries(v.columns)) cols[n] = column(v.types[n], xs);
    const scalars: Record<string, number | bigint | boolean | string> = {};
    for (const [n, x] of Object.entries(v.scalars)) scalars[n] = v.scalar_types[n] === 'Q' ? BigInt(x as string) : x;
    const bytes = encodeBatch(desc, cols, scalars);
    expect(Buffer.from(bytes).toString('base64')).toBe(v.protobuf_b64);
    // and back: protobuf-es decodes the same columns
    const back = fromBinary(desc, bytes) as unknown as Record<string, unknown>;
    const camel = (s: string) => s.replace(/_([a-z0-9])/g, (_m, c: string) => c.toUpperCase());
    for (const [n, xs] of Object.entries(v.columns)) {
      const got = [...(back[camel(n)] as Iterable<unknown>)].map((x) => (typeof x === 'bigint' ? x.toString() : x));
      expect(got, n).toEqual(xs);
    }
  });
});
