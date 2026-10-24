// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * Fetch by colour (owner request 2026-10-24: "multiple rods like in the beginning, and the robot
 * goes to the colour of the rod we choose"): its route and its bests, as pure functions (tested
 * in test/g2_fetch_colour.test.ts).
 *
 *   ?view=play&game=fetch_colour&colour=red|green|blue|yellow[&planner=<id>]
 *
 * A missing or unknown colour opens the colour choice. Bests are kept per colour and, as
 * Fetch Rush's are, per AUTO planner (A*'s key has no planner suffix).
 */
import type { PlayPlanner } from './planners';
import { fetchColour } from './rules_view';
import type { FetchColourId } from './session';

/** the rules the worker plays (coco_lab.games.FETCH_COLOUR_RULES; a test keeps them equal) */
export const FETCH_COLOUR_RULES = 1;

/** The colour a Fetch by colour link asks for, or null (show the choice). */
export const colourFromQuery = (q: URLSearchParams): FetchColourId | null => fetchColour(q.get('colour'));

/** The link that plays a colour (with `&planner=` when AUTO's planner is not A*). */
export const colourHref = (base: string, colour: FetchColourId, planner: PlayPlanner = 'astar') =>
  `${base}?view=play&game=fetch_colour&colour=${colour}${planner === 'astar' ? '' : `&planner=${planner}`}`;

/** The best-stars key for a colour: per rules, per colour, per AUTO planner (A* has no suffix). */
export const colourBestKey = (colour: FetchColourId, planner: PlayPlanner = 'astar') =>
  `coco.play.best.v1.g2-fetch-colour.r${FETCH_COLOUR_RULES}-${colour}${planner === 'astar' ? '' : `.planner-${planner}`}`;
