// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {it,expect,vi} from 'vitest';
import {loadAssetBytes} from '../src/arena/mesh_cache';
it('shares the low robot bytes across Case File opens and retries failed loads',async()=>{
 const old=globalThis.fetch;
 const fetch=vi.fn().mockResolvedValue({ok:true,arrayBuffer:async()=>new ArrayBuffer(4)});
 globalThis.fetch=fetch;
 try {
  const a=loadAssetBytes('/test/robot_low.glb'),b=loadAssetBytes('/test/robot_low.glb');
  expect(a).toBe(b);await a;await loadAssetBytes('/test/robot_low.glb');expect(fetch).toHaveBeenCalledTimes(1);
  fetch.mockResolvedValueOnce({ok:false});await expect(loadAssetBytes('/test/retry.glb')).rejects.toThrow(/Mesh/);
  await loadAssetBytes('/test/retry.glb');expect(fetch).toHaveBeenCalledTimes(3);
 }finally {globalThis.fetch=old;}
});
