// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R4: the learner's progress -- stars per lesson, hints used, whether the reference solution was
 * viewed, and the answer that passed (so a completion link can carry it). It lives in ONE pref
 * (prefs.ts, `coco.prefs.v1.course`; every storage access is inside prefs.ts's try), works
 * without storage (the page keeps it in memory), and is exported/imported as a JSON file.
 * Nothing leaves the browser unless the learner shares a link or a file.
 *
 * Stars are honest about help: 3 = passed with no hint; 2 = passed using the first two hint
 * levels; 1 = passed after the "nearly the answer" hint or after viewing the reference solution.
 */
import { readPref, writePref } from '../prefs';
import type { Answer } from './types';

export const PROGRESS_SCHEMA = 'coco.lesson.progress.v1';

export interface LessonProgress {
  /** the option chosen at Predict (first try only; it is a prediction, not a quiz) */
  predicted?: number;
  passed: boolean;
  /** highest hint level opened, 0..3 */
  hints: number;
  /** the reference solution was opened (only possible after a real attempt) */
  solution: boolean;
  attempts: number;
  /** the answer that passed (kept for completion links) and its grade digest */
  answer?: Answer;
  digest?: string;
  at?: string;
}
export interface Progress { schema: typeof PROGRESS_SCHEMA; lessons: Record<string, LessonProgress>; track?: string }

const empty = (): Progress => ({ schema: PROGRESS_SCHEMA, lessons: {} });

const isProgress = (v: unknown): v is Progress => {
  if (!v || typeof v !== 'object') return false;
  const p = v as Progress;
  if (p.schema !== PROGRESS_SCHEMA || !p.lessons || typeof p.lessons !== 'object') return false;
  return Object.values(p.lessons).every((l) => l && typeof l === 'object' && typeof l.passed === 'boolean'
    && Number.isInteger(l.hints) && l.hints >= 0 && l.hints <= 3 && typeof l.solution === 'boolean' && Number.isInteger(l.attempts));
};

let memory: Progress | null = null;

export function loadProgress(): Progress {
  if (!memory) memory = readPref('course', empty(), isProgress);
  return memory;
}

function save(p: Progress): void {
  memory = p;
  writePref('course', p);   // fails quietly without storage: the page still works this session
}

export function lessonProgress(id: string): LessonProgress {
  return loadProgress().lessons[id] ?? { passed: false, hints: 0, solution: false, attempts: 0 };
}

export function updateLesson(id: string, change: (l: LessonProgress) => LessonProgress): LessonProgress {
  const p = loadProgress();
  const next = change({ ...lessonProgress(id) });
  save({ ...p, lessons: { ...p.lessons, [id]: next } });
  return next;
}

export function stars(l: LessonProgress): 0 | 1 | 2 | 3 {
  if (!l.passed) return 0;
  if (l.solution || l.hints >= 3) return 1;
  return l.hints > 0 ? 2 : 3;
}

export function setTrack(track: string): void { save({ ...loadProgress(), track }); }

/** The progress as a downloadable JSON file's text. */
export function exportProgress(): string { return JSON.stringify(loadProgress(), null, 1) + '\n'; }

/** Replace the progress with an imported file's; throws with a reason for a file that is not one. */
export function importProgress(text: string): Progress {
  let v: unknown;
  try { v = JSON.parse(text); } catch { throw new Error('That file is not JSON.'); }
  if (!isProgress(v)) throw new Error(`That file is not a COCO Lab progress file (${PROGRESS_SCHEMA}).`);
  save(v);
  return v;
}

export function resetProgress(): void { save(empty()); }
