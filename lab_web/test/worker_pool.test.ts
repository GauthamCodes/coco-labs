// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
class FakeWorker {
  static made:FakeWorker[]=[];
  messages:unknown[]=[];
  onerror:(()=>void)|null=null;
  terminated=false;
  constructor(){FakeWorker.made.push(this);}
  postMessage(value:unknown){this.messages.push(value);}
  addEventListener(){}
  terminate(){this.terminated=true;}
}
beforeEach(()=>{vi.resetModules();FakeWorker.made=[];vi.stubGlobal('Worker',FakeWorker);});
afterEach(()=>vi.unstubAllGlobals());
describe('title interpreter ownership',()=>{
 it('warms once, without starting a model, and can be claimed only once',async()=>{
  const pool=await import('../src/arena/worker_pool');
  pool.warmModel();pool.warmModel();
  expect(FakeWorker.made).toHaveLength(1);
  expect(FakeWorker.made[0].messages).toEqual([expect.objectContaining({type:'warm'})]);
  expect(pool.claimWarmWorker(true)).toBe(FakeWorker.made[0]);
  expect(pool.claimWarmWorker(true)).toBe(FakeWorker.made[1]);
  expect(FakeWorker.made[1].messages).toEqual([]);
 });
 it('a CDN comparison cannot steal the self-hosted interpreter',async()=>{
  const pool=await import('../src/arena/worker_pool');pool.warmModel();
  expect(pool.claimWarmWorker(false)).toBe(FakeWorker.made[1]);
  expect(pool.claimWarmWorker(true)).toBe(FakeWorker.made[0]);
 });
 it('a failed warm worker is retired and may be retried',async()=>{
  const pool=await import('../src/arena/worker_pool');pool.warmModel();
  FakeWorker.made[0].onerror!();
  expect(FakeWorker.made[0].terminated).toBe(true);
  pool.warmModel();expect(FakeWorker.made).toHaveLength(2);
  expect(pool.claimWarmWorker(true)).toBe(FakeWorker.made[1]);
 });
});
