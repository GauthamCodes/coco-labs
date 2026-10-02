// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * coco.v1, as the Live tab speaks it: SHAPES ONLY.
 *
 * The wire contract is `docs/WEB_API.md`; the server is `coco_web`. JSON
 * frames are decoded by `JSON.parse`; binary sensor frames by coco_web's own
 * `web/frame.js` (see `./frame.ts`), never by a second decoder. Every client
 * frame here names an INTENT. None has a field that could carry a topic,
 * and `test/live.test.ts` asserts the set equals the server's `commands`
 * for the intents this tab sends.
 */

export const PROTOCOL = 'coco.v1';

export type UiMode = 'teleop' | 'auto' | 'stop';

export interface Pose2D { x: number; y: number; yaw: number; z?: number }

export interface Belief extends Pose2D {
  cov_xx: number | null; cov_yy: number | null; cov_yawyaw: number | null; age_s: number;
}

export interface Span { x0: number; x1: number }
export interface Bay {
  bay_id: string; platform_id?: string; y: number; width: number;
  ramp: Span; platform: Span; descent: Span;
}
export interface World {
  frame: 'map'; offset_x: number; bays?: Bay[];
  ramp: Span & { width: number }; platform: Span & { width: number };
  home: { x: number; y: number };
  targets: { colour: string; x: number; y: number; diameter: number }[];
}

export interface Limits {
  linear: number; angular: number; colours: string[]; modes: string[];
}

export interface Welcome {
  type: 'welcome'; protocol: string; commands: string[];
  limits: Limits; world?: World | null;
  /** Additive (Phase 2): this connection's id. */
  you?: string;
  /** Additive (Phase 2): did colours / depth clip / limits fall back? */
  config?: { source: 'coco_config' | 'fallback'; fallbacks: string[] };
}

export interface Mission {
  online: boolean; state: string | null; previous: string | null;
  words: string | null; active: boolean; colour: string | null;
  reason: string | null; reason_words: string | null; result: string | null;
  owner: string | null; mode: string | null; step: number | null;
  steps: number | null; recovering: boolean;
}

export interface Goal { x: number; y: number; sent_at: number; status: string }

export interface Telemetry {
  type: 'telemetry'; seq: number; t: number;
  robot: {
    pose: Pose2D | null; frame: string; localised: boolean;
    velocity: { linear: number; angular: number } | null; online: boolean;
    belief?: Belief | null; truth?: Pose2D | null;
  };
  mission: Mission | null;
  nav: {
    online: boolean; path: [number, number][]; active_source: string | null;
    local_path?: [number, number][]; goal?: Goal | null; path_rx?: number | null;
  };
  sensors: Record<string, unknown>;
  platform: {
    pilot: string | null; health: string;
    arbiter: { mode: string | null; active: string | null; online: boolean };
    stop?: { latched: boolean; since: number | null; violations: number };
    /** Additive (Phase 2 Part C): who may command COCO. */
    control?: Control;
  };
}

/** `platform.control`: open (local) or code (one driver, spectators). */
export interface Control {
  access: 'open' | 'code';
  over: string | null;
  driver?: boolean; driver_id?: string | null; clients?: number; max_clients?: number;
  idle_s?: number; idle_left_s?: number | null; session_left_s?: number; last_end?: string | null;
}

export interface MapFrame {
  type: 'map'; width: number; height: number; resolution: number;
  origin: { x: number; y: number }; data: string;
}

export interface ErrorFrame { type: 'error'; id: string | number | null; code: string; message: string }
export interface AckFrame { type: 'ack'; id: string | number | null; command: string; ok: true }

export type ServerFrame = Welcome | Telemetry | MapFrame | ErrorFrame | AckFrame
  | { type: 'pong'; t: number } | { type: 'subscription' };

/** Every client frame this tab can send. A closed set of intents. */
export type Intent =
  | { type: 'hello'; client: string; binary: boolean }
  | { type: 'ping'; t: number }
  | { type: 'drive'; linear: number; angular: number }
  | { type: 'stop' }
  | { type: 'set_mode'; mode: UiMode }
  | { type: 'select_target'; colour: string }
  | { type: 'mission'; action: 'start' | 'abort' }
  | { type: 'nav_goal'; x: number; y: number }
  | { type: 'subscribe'; streams: string[] }
  | { type: 'set_stream'; stream: 'camera'; fps?: number; quality?: number; scale?: number }
  | { type: 'claim'; code: string }
  | { type: 'release' };

/** The intent types this tab sends; each must be in welcome.commands. */
export const INTENT_TYPES: readonly Intent['type'][] = [
  'hello', 'ping', 'drive', 'stop', 'set_mode', 'select_target', 'mission',
  'nav_goal', 'subscribe', 'set_stream', 'claim', 'release',
];
