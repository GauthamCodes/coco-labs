// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Little-endian typed arrays out of a bundle's concatenated array bytes.
 *
 * The arrays are contiguous with NO alignment: `trace.kind` is N bytes of
 * u8, so the i32 column after it usually starts at an odd offset, and a
 * typed-array VIEW would throw `RangeError`. Every array is therefore
 * COPIED into its own aligned buffer. On a little-endian host the copy is
 * a byte slice; on a big-endian host (or when `forceDataView` is set, which
 * the tests do to pin the two paths equal) each element goes through a
 * `DataView` read with `littleEndian = true`.
 */

export type Dtype = 'u8' | 'i32' | 'f64';
export type TypedColumn = Uint8Array | Int32Array | Float64Array;

export const DTYPE_SIZE: Record<Dtype, number> = { u8: 1, i32: 4, f64: 8 };

export const HOST_LITTLE_ENDIAN = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;

export function readArray(
  raw: Uint8Array, offset: number, count: number, dtype: 'u8', forceDataView?: boolean): Uint8Array;
export function readArray(
  raw: Uint8Array, offset: number, count: number, dtype: 'i32', forceDataView?: boolean): Int32Array;
export function readArray(
  raw: Uint8Array, offset: number, count: number, dtype: 'f64', forceDataView?: boolean): Float64Array;
export function readArray(
  raw: Uint8Array, offset: number, count: number, dtype: Dtype, forceDataView?: boolean): TypedColumn;
export function readArray(
  raw: Uint8Array, offset: number, count: number, dtype: Dtype, forceDataView = false,
): TypedColumn {
  const size = DTYPE_SIZE[dtype];
  const start = raw.byteOffset + offset;
  const end = start + count * size;
  if (offset < 0 || offset + count * size > raw.length) {
    throw new RangeError(`array [${offset}, +${count * size}) outside ${raw.length} bytes`);
  }
  if (dtype === 'u8') return raw.slice(offset, offset + count);
  if (HOST_LITTLE_ENDIAN && !forceDataView) {
    const copy = raw.buffer.slice(start, end) as ArrayBuffer; // aligned: a fresh buffer
    return dtype === 'i32' ? new Int32Array(copy) : new Float64Array(copy);
  }
  const dv = new DataView(raw.buffer, start, count * size);
  if (dtype === 'i32') {
    const out = new Int32Array(count);
    for (let k = 0; k < count; k++) out[k] = dv.getInt32(4 * k, true);
    return out;
  }
  const out = new Float64Array(count);
  for (let k = 0; k < count; k++) out[k] = dv.getFloat64(8 * k, true);
  return out;
}

/** The little-endian bytes of a column (for hashing a decoded column). */
export function columnBytes(col: TypedColumn): Uint8Array {
  if (col instanceof Uint8Array) return col;
  if (HOST_LITTLE_ENDIAN) return new Uint8Array(col.buffer, col.byteOffset, col.byteLength);
  const out = new Uint8Array(col.byteLength);
  const dv = new DataView(out.buffer);
  if (col instanceof Int32Array) col.forEach((v, k) => dv.setInt32(4 * k, v, true));
  else col.forEach((v, k) => dv.setFloat64(8 * k, v, true));
  return out;
}
