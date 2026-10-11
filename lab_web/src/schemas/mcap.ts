// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The run container: MCAP, protobuf messages, zstd-compressed chunks
 * (README section 5.2; docs/v2/SCHEMAS.md "Container").
 *
 * - The manifest (coco.envelope.manifest.v1) is the first message, at
 *   log time 0, and the file's metadata record "coco" carries its run_id.
 * - Every channel's MCAP schema is the protobuf FileDescriptorSet of its
 *   message (encoding "protobuf"), so any MCAP tool can decode it.
 * - Message log time is t_world in nanoseconds (an integer); the MCAP
 *   `sequence` is the batch's first seq.
 *
 * Compression is injected: Node's built-in `zlib.zstdCompressSync` when a
 * build tool writes, none in the browser. Reading uses `fzstd` (pure JS).
 */

import { create, toBinary, fromBinary, type DescMessage, type Message } from '@bufbuild/protobuf';
import { FileDescriptorSetSchema, type FileDescriptorProto } from '@bufbuild/protobuf/wkt';
import { McapIndexedReader, McapStreamReader, McapWriter, TempBuffer } from '@mcap/core';
import { decompress as zstdDecompress } from 'fzstd';

import { ManifestSchema, type Manifest } from './gen/coco/envelope/v1/manifest_pb';

export const MANIFEST_CHANNEL = 'coco.envelope.manifest.v1';
export const PROFILE = 'coco';

export type Compressor = (data: Uint8Array) => Uint8Array;

/** One record to write: a channel, its message type, its encoded bytes. */
export interface RunRecord {
  channel: string;
  schema: DescMessage;
  data: Uint8Array;
  tWorld: number;     // seconds
  seq?: number;
}

function descriptorSet(desc: DescMessage): Uint8Array {
  // the message's file and every file it imports, dependencies first
  const files: FileDescriptorProto[] = [];
  const seen = new Set<string>();
  const visit = (f: DescMessage['file']) => {
    if (seen.has(f.name)) return;
    seen.add(f.name);
    for (const d of f.dependencies) visit(d);
    files.push(f.proto);
  };
  visit(desc.file);
  return toBinary(FileDescriptorSetSchema, create(FileDescriptorSetSchema, { file: files }));
}

const ns = (s: number) => BigInt(Math.round(s * 1e9));

/** Write a run: the manifest, then every record, in the order given. */
export async function writeRun(manifest: Manifest, records: RunRecord[], compress?: Compressor): Promise<Uint8Array> {
  const buf = new TempBuffer();
  const writer = new McapWriter({
    writable: buf,
    chunkSize: 1 << 20,
    compressChunk: compress ? (data) => ({ compression: 'zstd', compressedData: compress(data) }) : undefined,
  });
  await writer.start({ profile: PROFILE, library: 'coco_schemas (lab_web/src/schemas/mcap.ts)' });
  const channels = new Map<string, number>();
  const schemas = new Map<string, number>();
  const channelOf = async (name: string, desc: DescMessage) => {
    let id = channels.get(name);
    if (id !== undefined) return id;
    let sid = schemas.get(desc.typeName);
    if (sid === undefined) {
      sid = await writer.registerSchema({ name: desc.typeName, encoding: 'protobuf', data: descriptorSet(desc) });
      schemas.set(desc.typeName, sid);
    }
    id = await writer.registerChannel({ topic: name, schemaId: sid, messageEncoding: 'protobuf', metadata: new Map() });
    channels.set(name, id);
    return id;
  };
  const all: RunRecord[] = [{ channel: MANIFEST_CHANNEL, schema: ManifestSchema, data: toBinary(ManifestSchema, manifest), tWorld: 0 }, ...records];
  for (const r of all) {
    const channelId = await channelOf(r.channel, r.schema);
    const t = ns(r.tWorld);
    await writer.addMessage({ channelId, sequence: r.seq ?? 0, logTime: t, publishTime: t, data: r.data });
  }
  await writer.addMetadata({ name: 'coco', metadata: new Map([['run_id', manifest.runId]]) });
  await writer.end();
  return buf.get();
}

export interface ReadMessage { channel: string; schemaName: string; data: Uint8Array; logTime: bigint; sequence: number }

/** Read every message back, in log-time order. */
export async function readRun(bytes: Uint8Array): Promise<{ manifest: Manifest; messages: ReadMessage[]; profile: string }> {
  const readable = {
    size: async () => BigInt(bytes.byteLength),
    read: async (offset: bigint, size: bigint) => bytes.subarray(Number(offset), Number(offset + size)),
  };
  const reader = await McapIndexedReader.Initialize({
    readable,
    decompressHandlers: { zstd: (data: Uint8Array, size: bigint) => zstdDecompress(data, new Uint8Array(Number(size))) },
  });
  const messages: ReadMessage[] = [];
  for await (const m of reader.readMessages()) {
    const ch = reader.channelsById.get(m.channelId)!;
    const sc = reader.schemasById.get(ch.schemaId)!;
    messages.push({ channel: ch.topic, schemaName: sc.name, data: m.data, logTime: m.logTime, sequence: m.sequence });
  }
  const first = messages[0];
  if (!first || first.channel !== MANIFEST_CHANNEL) throw new Error('not a coco run: the manifest is not the first message');
  return { manifest: fromBinary(ManifestSchema, first.data), messages, profile: reader.header.profile };
}

/** A run file record by record, as written: what `repackRun` copies (M3.1). */
export interface RawRun {
  profile: string;
  schemas: Map<number, { name: string; encoding: string; data: Uint8Array }>;
  channels: Map<number, { topic: string; schemaId: number; messageEncoding: string; metadata: Map<string, string> }>;
  messages: { channelId: number; sequence: number; logTime: bigint; publishTime: bigint; data: Uint8Array }[];
  metadata: { name: string; metadata: Map<string, string> }[];
}

/**
 * Read a run file front to back (no index needed): what the Python writer
 * (`coco_schemas/mcap_write.py`, the ROS-to-event adapter's) produces --
 * uncompressed, no summary section. Compressed chunks are read too.
 */
export function readRawStream(bytes: Uint8Array): RawRun {
  const reader = new McapStreamReader({
    decompressHandlers: { zstd: (data: Uint8Array, size: bigint) => zstdDecompress(data, new Uint8Array(Number(size))) },
  });
  reader.append(bytes);
  const out: RawRun = { profile: '', schemas: new Map(), channels: new Map(), messages: [], metadata: [] };
  for (let r = reader.nextRecord(); r; r = reader.nextRecord()) {
    if (r.type === 'Header') out.profile = r.profile;
    else if (r.type === 'Schema') out.schemas.set(r.id, { name: r.name, encoding: r.encoding, data: r.data });
    else if (r.type === 'Channel') out.channels.set(r.id, { topic: r.topic, schemaId: r.schemaId, messageEncoding: r.messageEncoding, metadata: r.metadata });
    else if (r.type === 'Message') out.messages.push({ channelId: r.channelId, sequence: r.sequence, logTime: r.logTime, publishTime: r.publishTime, data: r.data });
    else if (r.type === 'Metadata') out.metadata.push({ name: r.name, metadata: r.metadata });
  }
  if (!reader.done()) throw new Error('not a whole MCAP file');
  return out;
}

/**
 * Re-chunk a run file for the site (M3.1/M3.3): the same schemas (their
 * descriptor bytes as written), channels, messages (bytes, times, sequence)
 * and metadata, in the same order, written with chunk indexes and, given a
 * compressor, zstd -- so `readRun` can seek it. Nothing is re-encoded.
 */
export async function repackRun(bytes: Uint8Array, compress?: Compressor, library = 'lab_web/src/schemas/mcap.ts repackRun'): Promise<Uint8Array> {
  return writeRaw(readRawStream(bytes), compress, library);
}

/** Write a RawRun record by record (schemas, channels, messages, metadata, in that order). */
export async function writeRaw(raw: RawRun, compress?: Compressor, library = 'lab_web/src/schemas/mcap.ts writeRaw',
  chunkSize = 1 << 20): Promise<Uint8Array> {
  const buf = new TempBuffer();
  const writer = new McapWriter({
    writable: buf,
    chunkSize,
    compressChunk: compress ? (data) => ({ compression: 'zstd', compressedData: compress(data) }) : undefined,
  });
  await writer.start({ profile: raw.profile, library });
  const schemaIds = new Map<number, number>();
  for (const [id, s] of raw.schemas) schemaIds.set(id, await writer.registerSchema(s));
  const channelIds = new Map<number, number>();
  for (const [id, c] of raw.channels) {
    channelIds.set(id, await writer.registerChannel({ ...c, schemaId: schemaIds.get(c.schemaId)! }));
  }
  for (const m of raw.messages) await writer.addMessage({ ...m, channelId: channelIds.get(m.channelId)! });
  for (const md of raw.metadata) await writer.addMetadata(md);
  await writer.end();
  return buf.get();
}

// -- Case File layout (M3 review, decision D6: scans load after the first frame) --

/** The channels a Case File defers until after its first frame is drawn (ADR 0005, amendment D6). */
export const DEFERRED_CHANNELS: readonly string[] = ['coco.sensor.scan.lidar.v1'];

const isDeferred = (topic: string) => DEFERRED_CHANNELS.includes(topic);

/**
 * The "ordered" layout: one file, every other message first (in its order), the deferred
 * channels' after them (in theirs). Nothing is re-encoded. Chunks are small (256 KiB
 * uncompressed by default) so the chunk holding both the last first-frame messages and
 * the first scans is small too.
 */
export async function orderCase(raw: RawRun, compress?: Compressor, chunkSize = 1 << 18,
  library = 'lab_web/src/schemas/mcap.ts orderCase'): Promise<Uint8Array> {
  const late = (m: RawRun['messages'][number]) => isDeferred(raw.channels.get(m.channelId)!.topic);
  return writeRaw({ ...raw, messages: [...raw.messages.filter((m) => !late(m)), ...raw.messages.filter(late)] },
    compress, library, chunkSize);
}

/**
 * Read an "ordered" Case File as it arrives. `onFirst` is called once, with the manifest
 * and every message before the first deferred one (or with all of them, if there is
 * none); the promise resolves with the deferred messages when the file has arrived.
 */
export async function streamCase(body: ReadableStream<Uint8Array>,
  onFirst: (run: { manifest: Manifest; messages: ReadMessage[] }) => void): Promise<ReadMessage[]> {
  const reader = new McapStreamReader({
    decompressHandlers: { zstd: (data: Uint8Array, size: bigint) => zstdDecompress(data, new Uint8Array(Number(size))) },
  });
  const schemas = new Map<number, string>();
  const channels = new Map<number, { topic: string; schemaId: number }>();
  const first: ReadMessage[] = [];
  const later: ReadMessage[] = [];
  let fired = false;
  const fire = () => {
    if (fired) return;
    fired = true;
    if (!first.length || first[0].channel !== MANIFEST_CHANNEL) throw new Error('not a coco run: the manifest is not the first message');
    first.sort((a, b) => (a.logTime < b.logTime ? -1 : a.logTime > b.logTime ? 1 : 0));
    onFirst({ manifest: fromBinary(ManifestSchema, first[0].data), messages: first });
  };
  const src = body.getReader();
  for (;;) {
    const { value, done } = await src.read();
    if (value) reader.append(value);
    for (let r = reader.nextRecord(); r; r = reader.nextRecord()) {
      if (r.type === 'Schema') schemas.set(r.id, r.name);
      else if (r.type === 'Channel') channels.set(r.id, { topic: r.topic, schemaId: r.schemaId });
      else if (r.type === 'Message') {
        const c = channels.get(r.channelId)!;
        const m = { channel: c.topic, schemaName: schemas.get(c.schemaId)!, data: r.data, logTime: r.logTime, sequence: r.sequence };
        if (isDeferred(c.topic)) { fire(); later.push(m); } else if (fired) throw new Error('a message after the deferred ones');
        else first.push(m);
      }
    }
    if (done) break;
  }
  if (!reader.done()) throw new Error('not a whole MCAP file');
  fire();
  return later;
}

/**
 * What a run file holds, independent of how it is chunked, compressed or laid out:
 * the profile, the metadata, and per channel its schema and every message (log time,
 * publish time, sequence, bytes) in order. Two files with equal digests hold exactly
 * the same content. `sha` is a sha256 over bytes (node:crypto in a tool or a test).
 */
export function contentDigest(raw: RawRun, sha: (b: Uint8Array) => string): Record<string, unknown> {
  const enc = new TextEncoder();
  const byChannel = new Map<number, Uint8Array[]>();
  for (const m of raw.messages) {
    const head = new Uint8Array(28);
    const dv = new DataView(head.buffer);
    dv.setBigUint64(0, m.logTime, true); dv.setBigUint64(8, m.publishTime, true);
    dv.setUint32(16, m.sequence, true); dv.setBigUint64(20, BigInt(m.data.byteLength), true);
    (byChannel.get(m.channelId) ?? byChannel.set(m.channelId, []).get(m.channelId)!).push(head, m.data);
  }
  const channels: Record<string, unknown> = {};
  // by topic, so the digest does not depend on the order a layout registered its channels in
  for (const [id, c] of [...raw.channels].sort(([, a], [, b]) => (a.topic < b.topic ? -1 : a.topic > b.topic ? 1 : 0))) {
    const s = raw.schemas.get(c.schemaId)!;
    const parts = byChannel.get(id) ?? [];
    const all = new Uint8Array(parts.reduce((n, p) => n + p.byteLength, 0));
    let o = 0;
    for (const p of parts) { all.set(p, o); o += p.byteLength; }
    channels[c.topic] = { messages: parts.length / 2, sha256: sha(all), encoding: c.messageEncoding,
      schema: s.name, schema_encoding: s.encoding, schema_sha256: sha(s.data) };
  }
  const meta = raw.metadata.map((md) => [md.name, [...md.metadata].sort()]);
  return { profile: raw.profile, messages: raw.messages.length, metadata_sha256: sha(enc.encode(JSON.stringify(meta))), channels };
}

export type { Message };
