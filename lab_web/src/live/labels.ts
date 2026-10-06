// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Every claim the Live tab makes about itself, in one place (rule 4, rule 5).
 * Each text is backed by a test or a measured result; the citation is beside
 * it, and `test/live.test.ts` pins the wording that must not drift.
 */

import type { Control, MissionSearch, Telemetry, Welcome } from './protocol';

/** Rule 4: the mode is labelled on screen. */
export function liveLabel(url: string): string {
  return isLocal(url) ? 'Live — local stack' : 'Live — remote session';
}

export function isLocal(url: string): boolean {
  try {
    const h = new URL(url).hostname;
    return h === 'localhost' || h === '127.0.0.1' || h === '[::1]';
  } catch {
    return false;
  }
}

/**
 * The TOLD mission (`mission.launch.py search:=false`): it resolves the
 * colour's bay with resolve_lane() -- the episode's region map, or with none,
 * exactly lane_for_colour() -- and does not search. Until Phase 5 this was
 * the only autonomous mode, and the page always said so.
 */
export const LANE_TOLD =
  'Honest label: this mission was launched TOLD (search:=false): it is told ' +
  'which bay this colour is in (resolve_lane() / lane_for_colour()) and does ' +
  'not search for the target.';

/** Phase 5: what a mission that reports mode=discover does. */
export const DISCOVERS =
  'The robot discovers the target: it is told only the colour, then searches ' +
  "the bays in the order coco_lab chooses (least expected search cost, " +
  're-planned after every look). No bay and no position reaches it; the ' +
  'camera finds the target.';

/** Until the running mission says which it is, no claim either way. */
export const SEARCH_UNKNOWN =
  'The running mission has not reported whether it searches, so this page ' +
  'claims neither: an older stack is told the bay.';

/**
 * The autonomous mode's honest label, from what the RUNNING mission
 * reports (`/mission/search`), never from a constant: a stack launched
 * search:=false, or one from before Phase 5, is labelled told.
 */
export function autonomousLabel(search: MissionSearch | null | undefined):
  { kind: 'discover' | 'told' | 'unknown'; text: string } {
  if (search?.online && search.mode === 'discover') return { kind: 'discover', text: DISCOVERS };
  if (search?.online && search.mode === 'told') return { kind: 'told', text: LANE_TOLD };
  return { kind: 'unknown', text: SEARCH_UNKNOWN };
}

/** One line of search progress, from the mission's own report; null when it is not searching. */
export function searchLine(search: MissionSearch | null | undefined): string | null {
  if (!search?.online || search.mode !== 'discover') return null;
  const parts: string[] = [];
  if (search.discovered) parts.push(`found in ${search.discovered}`);
  if (search.searched.length) parts.push(`searched: ${search.searched.join(', ')}`);
  if (search.current && !search.discovered) parts.push(`now: ${search.current}`);
  if (search.seen.length) parts.push(`last look saw ${search.seen.join(', ')}`);
  if (search.belief.length === search.regions.length && search.regions.length) {
    parts.push(`belief ${search.regions.map((r, i) => `${r} ${Math.round(search.belief[i] * 100)}%`).join(' · ')}`);
  }
  return parts.length ? `Search: ${parts.join('; ')}` : 'Search: not started';
}

/** Shown when the server's colours, depth clip or limits are defaults. */
export function fallbackWarning(welcome: Welcome | null): string | null {
  const c = welcome?.config;
  if (!c || c.source !== 'fallback') return null;
  return `This server is running on FALLBACK configuration: coco_config did not ` +
    `load (${c.fallbacks.join(', ') || 'unknown'}), so colours, depth clip or ` +
    `limits are built-in defaults, not the robot's own.`;
}

/**
 * This tab's role. `open`: anyone connected may command (local stack).
 * `driver` / `spectator`: a code-access session, decided by the SERVER
 * (coco_web/control.py); the page only reads it.
 */
export type Role = 'open' | 'driver' | 'spectator';
export function role(t: Telemetry | null, you: string | undefined): Role {
  const c = t?.platform.control;
  if (!c || c.access !== 'code') return 'open';
  return c.driver_id && you && c.driver_id === you ? 'driver' : 'spectator';
}

/** What a refusal code means to the person who got it. */
export function refusalWords(code: string, message: string): string {
  switch (code) {
    case 'stopped': return 'Stopped — pick a mode to move again.';
    case 'spectator': return 'You are watching. Only the driver, who entered the control code, can command COCO.';
    case 'bad_code': return 'That control code is not right for this session.';
    case 'driver_present': return 'Someone else is driving. Control passes only when they let go or go idle.';
    case 'rate_limited': return 'Too many commands at once; slow down.';
    case 'session_over': return 'This live session has ended. COCO is stopped.';
    case 'session_full': return 'This live session is full. Try again later.';
    default: return message;
  }
}

/** Who holds the stick, from this tab's point of view. */
export function controlHolder(t: Telemetry | null, you: string | undefined): string {
  if (!t) return 'unknown';
  const c = t.platform.control;
  if (c && c.access === 'code') {
    if (c.over) return 'nobody — the session has ended';
    if (role(t, you) === 'driver') return 'you (the driver)';
    return c.driver ? 'the driver (another person)' : 'nobody — enter the control code to drive';
  }
  const pilot = t.platform.pilot;
  const active = t.platform.arbiter?.active ?? null;
  if (pilot && you && pilot === you) return 'you';
  if (pilot) return 'another browser';
  if (active && active !== 'teleop') return 'the robot (autonomous)';
  return 'nobody';
}

/** The arbiter's forwarded source, in words. */
export function sourceWords(active: string | null | undefined): string {
  switch (active) {
    case 'teleop': return 'teleop (a person)';
    case 'nav': return 'Nav2';
    case 'rl': return 'the RL ramp policy';
    case 'approach': return 'the visual approach';
    default: return 'nothing (wheels held still)';
  }
}

/** True while a person is overriding a running mission. */
export function overriding(t: Telemetry | null): boolean {
  return !!t && !!t.mission?.active && t.platform.arbiter?.active === 'teleop';
}

/** Why the Live map may not yet show a localised pose. */
export function localisationNote(t: Telemetry | null): string | null {
  if (!t || !t.robot.online) return null;
  return t.robot.localised ? null : 'Not localised yet: the pose is odometry only.';
}

/**
 * The driver's idle line. While a mission or a Nav2 goal runs, AUTONOMY
 * holds the inactivity lease and the idle clock is suspended (coco_web
 * control.py; test_control.py::test_autonomy_is_not_driver_activity). Say
 * so, rather than show a countdown that does not move. The session cap is
 * never suspended.
 */
export function idleLine(ctl: Control | null | undefined): string {
  if (!ctl || ctl.access !== 'code') return '';
  if (ctl.lease === 'autonomy') return ' Idle release paused: autonomy is running (the session cap still applies).';
  if (ctl.idle_left_s != null) return ` Idle release in ${Math.ceil(ctl.idle_left_s)} s.`;
  return '';
}
