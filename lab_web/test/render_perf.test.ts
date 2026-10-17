// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {it,expect} from 'vitest';
import {Perf} from '../src/arena/perf';
it('FPS reports submitted frames and ages them out while rendering is paused',()=>{
 const perf=new Perf(),now=performance.timeOrigin+performance.now();
 perf.frame(now-100);perf.frame(now-50);
 expect(perf.snapshot().fps).toBe(2);
 const hidden=new Perf();hidden.frame(now-2000);expect(hidden.snapshot().fps).toBe(0);
});
