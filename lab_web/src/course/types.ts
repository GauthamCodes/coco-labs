// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R4: the Learn course's data (generated/course.json, written by lab_web/tools/course.py from
 * lab_web/course/*.yaml and coco_lab/coco_lab/course/exercises.v1.json). coco.lesson.v1, ADR 0015.
 * The page renders and asks the grader; it decides nothing about correctness itself.
 */
import type { ArenaLink } from '../learn/links';

export type Track = 'explorer' | 'builder' | 'researcher';
export const TRACKS: { id: Track; title: string; blurb: string; phone: string }[] = [
  { id: 'explorer', title: 'Explorer', blurb: 'No code. Predict, watch, tune parameters and find where a run went wrong.', phone: 'Fully playable on a phone.' },
  { id: 'builder', title: 'Builder', blurb: 'Fill in one function -- a heuristic, a resampler, a goal check -- and the page checks it exactly.', phone: 'Readable on a phone; coding is easier on a laptop.' },
  { id: 'researcher', title: 'Researcher', blurb: 'Write a whole algorithm, benchmark it, submit it to the leaderboard and run it in ROS 2.', phone: 'Readable on a phone; coding is easier on a laptop.' },
];
export const STEPS = ['predict', 'observe', 'explain', 'try', 'check', 'ros2'] as const;
export type Step = typeof STEPS[number];
export const STEP_TITLE: Record<Step, string> = {
  predict: 'Predict', observe: 'Observe', explain: 'Explain', try: 'Try', check: 'Check', ros2: 'In real ROS 2',
};

export interface Claim { id: string; label: string; text: string; evidence?: string[]; resolved: string[] }
export interface Observe {
  text: string;
  experiment?: { family: string; world: string; algorithms: string[]; from: string };
  arena?: ArenaLink;
  studio?: string;
  timeline?: string;
  link?: { view: string; tab?: string };
}
export interface Lesson {
  id: string; track: Track; title: string; predict: string; try: string;
  observe: Observe;
  explain: { text: string; diagram: string; claims?: string[] };
  ros2: { text: string; label: string; claims: string[] };
}
export interface Module {
  id: string; number: number; title: string; question: string; mission?: string;
  lessons: Lesson[]; claims: Claim[];
}
export interface Scenario { id: string; start: number[]; goal: number[]; seed: number; config?: string[]; zone?: number[] }
export interface Check { kind: string; label?: string; metric?: string; vs?: string; value?: number; window?: number; function?: string }
export interface Exercise {
  id: string; type: 'predict' | 'tune' | 'failure' | 'code' | 'benchmark'; seed: number;
  question?: string; options?: string[]; answer?: number; misconceptions?: Record<string, string>;
  family?: string; world?: string; algorithm?: string;
  params?: Record<string, { min: number; max: number; step: number; default: number; label: string }>;
  fixed_params?: Record<string, number>;
  compare?: Record<string, { algorithm?: string; params?: Record<string, number>; solution?: boolean; starter?: boolean }>;
  checks?: Check[]; hints?: string[];
  starter_code?: string; solution_code?: string; functions?: string[]; entry?: string;
  public_scenarios?: Scenario[]; run?: { name: string }; scenario?: Scenario;
  timeline?: { columns: string[]; series: number[][]; status: string; ticks: number };
  max_ticks?: number;
}
export interface GlossaryTerm { term: string; module: number; text: string }
export interface Course {
  schema: 'coco.lesson.v1'; version: number; modules: Module[];
  exercises: Record<string, Exercise>; glossary: GlossaryTerm[]; max_explain_words: number;
}

/** One check's verdict (coco_lab.course._result). */
export interface CheckResult {
  check: string; label: string; passed: boolean; which: 'public' | 'hidden'; scenario: string | null;
  measured: unknown; target: unknown; message: string;
}
/** coco.lesson.grade.v1 */
export interface Grade {
  schema: 'coco.lesson.grade.v1'; exercise: string; type: string; answer_sha256: string; passed: boolean;
  checks_passed: number; checks: number; results: CheckResult[]; digest: string;
  scenarios?: { public: Scenario[]; hidden: Scenario[] };
}
export type Answer = { choice?: number; tick?: number; params?: Record<string, number>; code?: string };

export function findLesson(c: Course, id: string): { module: Module; lesson: Lesson } | null {
  for (const m of c.modules) for (const l of m.lessons) if (l.id === id) return { module: m, lesson: l };
  return null;
}
