// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import limits from '../../../coco_lab/coco_lab/link_limits.json' with { type: 'json' };
import { Inflate } from 'three/addons/libs/fflate.module.js';
export const LIMITS = Object.freeze({ ...limits, z: Math.floor(limits.encoded * 3 / 4) });
export function boundedId(value, field, underscore = false) {
  if (typeof value !== 'string' || !value.length || value.length > LIMITS.id ||
      !(underscore ? /^[a-z0-9_-]+$/ : /^[a-z0-9-]+$/).test(value)) throw new Error(`Invalid ${field} link field`);
  return value;
}
export function boundedTick(value, field = 'tick', max = LIMITS.ticks) {
  if (!Number.isSafeInteger(value) || value < 0 || value > max) throw new Error(`Link ${field} must be between 0 and ${max}`);
}
export function boundedInputs(inputs, compact = false, end = LIMITS.ticks) {
  if (!Array.isArray(inputs) || inputs.length > LIMITS.inputs) throw new Error(`Link permits at most ${LIMITS.inputs} inputs`);
  let prev = -1;
  for (let k = 0; k < inputs.length; k++) {
    const tick = compact ? inputs[k]?.[0] : inputs[k]?.tick;
    // Non-driving challenges contain paths, bay names or computation indices, not tick logs.
    if (!compact && tick === undefined) continue;
    boundedTick(tick);
    if (tick < prev || tick > end) throw new Error('Link input ticks are out of order or beyond the run');
    if (k === 0) boundedTick(tick, 'first tick', LIMITS.first_tick);
    prev = tick;
  }
}
export function boundedJson(param, compressed = false) {
  if (typeof param !== 'string' || !param.length || param.length > LIMITS.encoded || !/^[A-Za-z0-9_-]+$/.test(param)) throw new Error(`Link encoded payload exceeds ${LIMITS.encoded} characters or is malformed`);
  const bin = atob(param.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - param.length % 4) % 4));
  let bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
  if (compressed) {
    let n = 0; const chunks = [];
    const stream = new Inflate(chunk => {
      n += chunk.length;
      if (n > LIMITS.json) throw new Error(`Link JSON exceeds ${LIMITS.json} bytes`);
      chunks.push(chunk);
    });
    // Limit each decompression allocation/work unit, including a crafted compression bomb.
    for (let i = 0; i < bytes.length; i += 64) stream.push(bytes.subarray(i, i + 64), i + 64 >= bytes.length);
    bytes = new Uint8Array(n); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  }
  if (bytes.length > LIMITS.json) throw new Error(`Link JSON exceeds ${LIMITS.json} bytes`);
  return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
}
export function validateSubmission(s) {
  boundedId(s.challenge, 'challenge'); boundedId(s.level, 'level');
  const i = s.inputs;
  if (Array.isArray(i)) boundedInputs(i);
  else if (i && typeof i === 'object') {
    boundedTick(i.ticks, 'ticks'); boundedInputs(i.log, false, i.ticks);
  } else throw new Error('Link has no input log');
}
export function decodeChallenge(q) {
  const c = q.get('c'), l = q.get('l'), z = q.get('z'), s = q.get('s');
  if (!c || !l || !(z || s)) throw new Error('not a Play challenge link');
  boundedId(c, 'challenge'); boundedId(l, 'level');
  // Validate all present fields, even one that would otherwise be ignored.
  if (s) boundedJson(s);
  const j = boundedJson(z || s, !!z);
  if (j.v !== 1 || !/^[0-9a-f]{64}$/.test(j.h ?? '') || !/^[0-9a-f]{64}$/.test(j.r ?? '') || ![1, 2].includes(j.hv ?? 1)) throw new Error('Malformed challenge link or hash version');
  const submission = { v: 1, challenge: c, level: l, level_hash: j.h, inputs: j.i };
  if (j.hv !== undefined) submission.hash_version = j.hv;
  validateSubmission(submission);
  return { submission, result_hash: j.r };
}

export function urlFieldError(params) {
  try {
    for (const key of ['c', 'l', 'challenge', 'replay', 'casefile', 'play', 'pl']) {
      if (params.has(key)) boundedId(params.get(key), key, ['replay','casefile'].includes(key));
    }
    for (const key of ['run', 's', 'z']) {
      const value = params.get(key);
      if (value && value.length > LIMITS.encoded) throw new Error(`Link ${key} exceeds ${LIMITS.encoded} characters`);
    }
    return null;
  } catch (e) { return String(e.message); }
}
