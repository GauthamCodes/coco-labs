// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The fast path of ADR 0001: encode a columnar event batch (the typed
 * arrays the worker posts) straight into its protobuf `*Batch` message,
 * without building one JavaScript object per event.
 *
 * The field table comes from the GENERATED descriptor (`gen/`), so a column
 * is found by its proto field name (`parent_row`, `t_world`), the same name
 * coco_lab's emitter uses. Output is byte-identical to Python protobuf's
 * `SerializeToString()` of the same message (proto3: packed numeric lists,
 * fields in number order, zero scalars omitted); test/schemas.test.ts pins
 * that against coco_schemas' vectors.
 */

import { ScalarType, type DescField, type DescMessage } from '@bufbuild/protobuf';
import { BinaryWriter, WireType } from '@bufbuild/protobuf/wire';

export type Column = ArrayLike<number> | ArrayLike<bigint> | ArrayLike<boolean> | ArrayLike<string>;

type Put = (w: BinaryWriter, v: never) => void;

function writerFor(t: ScalarType): Put {
  switch (t) {
    case ScalarType.DOUBLE: return (w, v: number) => { w.double(v); };
    case ScalarType.FLOAT: return (w, v: number) => { w.float(v); };
    case ScalarType.INT32: return (w, v: number) => { w.int32(v); };
    case ScalarType.SINT32: return (w, v: number) => { w.sint32(v); };
    case ScalarType.UINT32: return (w, v: number) => { w.uint32(v); };
    case ScalarType.INT64: return (w, v: bigint | number) => { w.int64(v); };
    case ScalarType.SINT64: return (w, v: bigint | number) => { w.sint64(v); };
    case ScalarType.UINT64: return (w, v: bigint | number) => { w.uint64(v); };
    case ScalarType.BOOL: return (w, v: boolean) => { w.bool(v); };
    case ScalarType.STRING: return (w, v: string) => { w.string(v); };
    default: throw new Error(`column type ${ScalarType[t]} is not supported`);
  }
}

function scalarOf(f: DescField): ScalarType {
  if (f.fieldKind === 'list') return f.listKind === 'enum' ? ScalarType.INT32 : f.listKind === 'scalar' ? f.scalar : -1 as ScalarType;
  if (f.fieldKind === 'scalar') return f.scalar;
  if (f.fieldKind === 'enum') return ScalarType.INT32;
  return -1 as ScalarType;
}

const isZero = (v: unknown) => v === 0 || v === 0n || v === false || v === '' || v === undefined;

/**
 * Encode `columns` (by proto field name) and per-batch `scalars` as `desc`.
 * Every column must have the same length; a missing column is empty.
 */
export function encodeBatch(desc: DescMessage, columns: Record<string, Column>,
  scalars: Record<string, number | bigint | boolean | string> = {}): Uint8Array {
  let n = -1;
  const w = new BinaryWriter();
  const fields = [...desc.fields].sort((a, b) => a.number - b.number);
  for (const f of fields) {
    const t = scalarOf(f);
    if (f.fieldKind === 'list') {
      const col = columns[f.name];
      if (!col || col.length === 0) continue;
      if (n < 0) n = col.length;
      const put = writerFor(t);
      if (t === ScalarType.STRING) {
        for (let k = 0; k < col.length; k += 1) put(w.tag(f.number, WireType.LengthDelimited), col[k] as never);
      } else {
        w.tag(f.number, WireType.LengthDelimited).fork();
        for (let k = 0; k < col.length; k += 1) put(w, col[k] as never);
        w.join();
      }
    } else if (f.fieldKind === 'scalar' || f.fieldKind === 'enum') {
      const v = scalars[f.name];
      if (isZero(v)) continue;
      const wire = t === ScalarType.DOUBLE || t === ScalarType.FIXED64 ? WireType.Bit64
        : t === ScalarType.FLOAT ? WireType.Bit32 : t === ScalarType.STRING ? WireType.LengthDelimited : WireType.Varint;
      writerFor(t)(w.tag(f.number, wire), v as never);
    } else {
      throw new Error(`${desc.typeName}.${f.name}: only scalar and list fields are columnar`);
    }
  }
  const unknown = Object.keys(columns).filter((k) => !desc.fields.some((f) => f.name === k));
  if (unknown.length) throw new Error(`${desc.typeName} has no fields ${unknown.join(', ')}`);
  return w.finish();
}
