// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import type { InputRow } from './protocol';
/** The scored race and the live race admit the same two input kinds. */
export function raceInputs<T extends Pick<InputRow, 'kind'>>(rows: T[], locked: boolean): T[] {
  return locked ? rows.filter(r => r.kind === 'teleop' || r.kind === 'stop') : rows;
}
