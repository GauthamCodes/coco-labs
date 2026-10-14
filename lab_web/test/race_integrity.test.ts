// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { expect, it } from 'vitest';
import { raceInputs } from '../src/arena/race_integrity';
it('a scored live race cannot submit planner, grasp, autonomy or other assisted inputs', () => {
  const rows = ['planner','grasp','autonomy','goal','config','reset','kidnap','teleop','stop'].map(kind => ({kind: kind as any}));
  expect(raceInputs(rows,true).map(r=>r.kind)).toEqual(['teleop','stop']);
  expect(raceInputs(rows,false)).toBe(rows);
});
