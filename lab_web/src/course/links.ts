// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R4: course links. Everything travels in the URL fragment (`#done=` / `#assign=`), which browsers
 * never send to a server; the payload is deflate-compressed JSON in base64url, as the Studio's code
 * links (R2.5). No server, no account.
 *
 * - A completion link carries a learner's answers (choices, ticks, slider values, files), the hints
 *   they used and whether they viewed a solution, and optionally a name THEY typed. Whoever opens it
 *   re-grades every answer in their own browser: "self-verified, not proctored" -- the hints and
 *   the name are what the learner declares; the pass/fail is recomputed.
 * - An assignment link carries a teacher's chosen lessons, an optional deadline label and whether to
 *   ask for a name. It holds no student data.
 */
import type { Answer } from './types';

export const COURSE_LINK_VERSION = 1;
export const COURSE_LINK_LIMIT = 96 * 1024;

export interface CompletionEntry { lesson: string; exercise: string; answer: Answer; hints: number; solution: boolean }
export interface Completion {
  v: number; kind: 'completion'; title: string; name?: string; assignment?: string; issued: string;
  entries: CompletionEntry[];
}
export interface Assignment { v: number; kind: 'assignment'; title: string; lessons: string[]; deadline?: string; askName: boolean }

function b64url(bytes: Uint8Array): string {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function unb64url(s: string): Uint8Array {
  const b = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4));
  return Uint8Array.from(b, (c) => c.charCodeAt(0));
}
async function pipe(bytes: Uint8Array, stream: CompressionStream | DecompressionStream): Promise<Uint8Array> {
  const out = new Response(new Blob([bytes as Uint8Array<ArrayBuffer>]).stream().pipeThrough(stream));
  return new Uint8Array(await out.arrayBuffer());
}
async function pack(obj: unknown): Promise<string> {
  const s = b64url(await pipe(new TextEncoder().encode(JSON.stringify(obj)), new CompressionStream('deflate-raw')));
  if (s.length > COURSE_LINK_LIMIT) throw new Error(`This link would be ${Math.round(s.length / 1024)} KB; at most ${COURSE_LINK_LIMIT / 1024} KB. Export your progress as a file instead.`);
  return s;
}
async function unpack(s: string): Promise<unknown> {
  if (!/^[A-Za-z0-9_-]+$/.test(s) || s.length > COURSE_LINK_LIMIT) throw new Error('This link is damaged or too long.');
  return JSON.parse(new TextDecoder().decode(await pipe(unb64url(s), new DecompressionStream('deflate-raw'))));
}

const clean = (s: unknown, n: number) => (typeof s === 'string' ? s.replace(/[\u0000-\u001f<>]/g, '').slice(0, n) : undefined);
const isAnswer = (a: unknown): a is Answer => {
  if (!a || typeof a !== 'object' || Array.isArray(a)) return false;
  const o = a as Record<string, unknown>;
  const keys = Object.keys(o);
  if (!keys.every((k) => ['choice', 'tick', 'params', 'code'].includes(k))) return false;
  if ('choice' in o && !Number.isInteger(o.choice)) return false;
  if ('tick' in o && !Number.isInteger(o.tick)) return false;
  if ('code' in o && typeof o.code !== 'string') return false;
  if ('params' in o && (typeof o.params !== 'object' || o.params === null || !Object.values(o.params).every((v) => typeof v === 'number' && Number.isFinite(v)))) return false;
  return true;
};

export async function completionFragment(c: Omit<Completion, 'v' | 'kind'>): Promise<string> {
  return `done=${await pack({ v: COURSE_LINK_VERSION, kind: 'completion', ...c })}`;
}

export async function readCompletion(fragment: string): Promise<Completion> {
  const m = /^#?done=([A-Za-z0-9_-]+)$/.exec(fragment.trim());
  if (!m) throw new Error('Not a completion link (it has no #done= part).');
  const o = await unpack(m[1]) as Record<string, unknown>;
  if (!o || o.v !== COURSE_LINK_VERSION || o.kind !== 'completion' || !Array.isArray(o.entries)) throw new Error('Not a COCO Lab completion link this version can read.');
  const entries: CompletionEntry[] = [];
  for (const e of o.entries.slice(0, 64) as Record<string, unknown>[]) {
    if (!e || typeof e.lesson !== 'string' || typeof e.exercise !== 'string' || !isAnswer(e.answer)) throw new Error('A damaged entry in the link.');
    entries.push({ lesson: e.lesson.slice(0, 64), exercise: e.exercise.slice(0, 64), answer: e.answer,
      hints: Number.isInteger(e.hints) ? Math.max(0, Math.min(3, e.hints as number)) : 0, solution: e.solution === true });
  }
  return { v: COURSE_LINK_VERSION, kind: 'completion', title: clean(o.title, 120) ?? '', name: clean(o.name, 80) || undefined,
    assignment: clean(o.assignment, 120) || undefined, issued: clean(o.issued, 40) ?? '', entries };
}

export async function assignmentFragment(a: Omit<Assignment, 'v' | 'kind'>): Promise<string> {
  return `assign=${await pack({ v: COURSE_LINK_VERSION, kind: 'assignment', ...a })}`;
}

export async function readAssignment(fragment: string): Promise<Assignment> {
  const m = /^#?assign=([A-Za-z0-9_-]+)$/.exec(fragment.trim());
  if (!m) throw new Error('Not an assignment link.');
  const o = await unpack(m[1]) as Record<string, unknown>;
  if (!o || o.v !== COURSE_LINK_VERSION || o.kind !== 'assignment' || !Array.isArray(o.lessons)) throw new Error('Not a COCO Lab assignment link this version can read.');
  return { v: COURSE_LINK_VERSION, kind: 'assignment', title: clean(o.title, 120) ?? 'Assignment',
    lessons: (o.lessons as unknown[]).filter((x): x is string => typeof x === 'string').slice(0, 64),
    deadline: clean(o.deadline, 60) || undefined, askName: o.askName === true };
}

/** A CSV cell: quoted, with formula-looking text neutralised (a spreadsheet must not run it). */
export function csvCell(v: unknown): string {
  let s = v === null || v === undefined ? '' : String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return `"${s.replace(/"/g, '""')}"`;
}
