// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Arena's controls (M4.5; README §5.5): actions, their default keys, and
 * remapping. Keys are `KeyboardEvent.code` values (where the key IS, not
 * what it types), so W A S D sit under the same fingers on any layout.
 * Every binding is remappable and stored through the preferences module.
 */

import { readPref, resetPref, writePref } from '../prefs';

export type Action =
  | 'forward' | 'reverse' | 'left' | 'right' | 'precision'
  | 'stop' | 'release' | 'context' | 'autonomy'
  | 'camera_next' | 'camera_follow' | 'robot_vision'
  | 'lens_1' | 'lens_2' | 'lens_3' | 'lens_4' | 'lens_5'
  | 'pause' | 'step_back' | 'step_forward' | 'help';

/** What each action does, in the words the help shows (README §5.5's table). */
export const ACTIONS: { id: Action; label: string }[] = [
  { id: 'forward', label: 'Forward' },
  { id: 'reverse', label: 'Reverse' },
  { id: 'left', label: 'Turn left' },
  { id: 'right', label: 'Turn right' },
  { id: 'precision', label: 'Precision (half speed, held)' },
  { id: 'stop', label: 'STOP (latched)' },
  { id: 'release', label: 'Release STOP; hold to reset home' },
  { id: 'context', label: 'Grasp or release (through the proximity gate)' },
  { id: 'autonomy', label: 'Hand the wheels back to autonomy' },
  { id: 'robot_vision', label: 'Robot vision overlays (Play)' },
  { id: 'camera_next', label: 'Next camera' },
  { id: 'camera_follow', label: 'Back to the follow camera' },
  { id: 'lens_1', label: 'Lens 1' }, { id: 'lens_2', label: 'Lens 2' }, { id: 'lens_3', label: 'Lens 3' },
  { id: 'lens_4', label: 'Lens 4' }, { id: 'lens_5', label: 'Lens 5' },
  { id: 'pause', label: 'Pause' },
  { id: 'step_back', label: 'Step back' },
  { id: 'step_forward', label: 'Step forward' },
  { id: 'help', label: 'Help' },
];

export type Bindings = Record<Action, string[]>;

export const DEFAULT_BINDINGS: Bindings = {
  forward: ['KeyW', 'ArrowUp'], reverse: ['KeyS', 'ArrowDown'], left: ['KeyA', 'ArrowLeft'], right: ['KeyD', 'ArrowRight'],
  precision: ['ShiftLeft', 'ShiftRight'],
  stop: ['Space'], release: ['KeyR'], context: ['KeyE'], autonomy: ['Tab'],
  robot_vision: ['KeyX'], camera_next: ['KeyC'], camera_follow: ['KeyV'],
  lens_1: ['Digit1'], lens_2: ['Digit2'], lens_3: ['Digit3'], lens_4: ['Digit4'], lens_5: ['Digit5'],
  pause: ['KeyP'], step_back: ['BracketLeft'], step_forward: ['BracketRight'], help: ['KeyH'],
};

/** Holding the release key this long resets the robot home (ms). */
export const HOLD_TO_RESET_MS = 1000;

const isBindings = (v: unknown): v is Partial<Bindings> => typeof v === 'object' && v !== null && !Array.isArray(v)
  && Object.entries(v).every(([k, codes]) => ACTIONS.some((a) => a.id === k) && Array.isArray(codes)
    && codes.every((c) => typeof c === 'string' && /^[A-Za-z0-9]{1,24}$/.test(c)));

/** The bindings in force: the stored remaps over the defaults. */
export function loadBindings(): Bindings {
  const own = readPref<Partial<Bindings>>('keys', {}, isBindings);
  return { ...DEFAULT_BINDINGS, ...own };
}

/** The action a key code triggers, if any. */
export function actionFor(code: string, b: Bindings): Action | null {
  for (const a of ACTIONS) if (b[a.id].includes(code)) return a.id;
  return null;
}

/**
 * Bind `code` to `action` as its first key. A key does one thing: it is taken off any other action.
 * Only the changes from the defaults are stored.
 */
export function rebind(b: Bindings, action: Action, code: string): Bindings {
  const next = { ...b } as Bindings;
  for (const a of ACTIONS) next[a.id] = b[a.id].filter((c) => c !== code);
  next[action] = [code, ...next[action].filter((c) => c !== code)].slice(0, 2);
  const changed = Object.fromEntries(ACTIONS.filter((a) => next[a.id].join() !== DEFAULT_BINDINGS[a.id].join())
    .map((a) => [a.id, next[a.id]]));
  if (Object.keys(changed).length) writePref('keys', changed); else resetPref('keys');
  return next;
}

export function resetBindings(): Bindings {
  resetPref('keys');
  return { ...DEFAULT_BINDINGS };
}

/** A key code as the help shows it. */
export function keyLabel(code: string): string {
  return code.replace(/^Key/, '').replace(/^Digit/, '').replace(/^Arrow(.*)/, '$1 arrow')
    .replace(/^BracketLeft$/, '[').replace(/^BracketRight$/, ']').replace(/^Shift(Left|Right)$/, 'Shift');
}
