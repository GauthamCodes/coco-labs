// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {it,expect} from 'vitest';
import {scanArea} from '../src/arena/render/scanArea';
it('scan fan connects valid adjacent endpoints and only lights actual hits',()=>{
 const result=scanArea(new Float32Array([0,0,0,1,0,0,0,0,0,0,2,0,0,0,0,-3,0,0]),3);
 expect([...result.triangles]).toEqual([0,0,0,1,0,0,0,2,0,0,0,0,0,2,0,-3,0,0]);
 expect([...result.hits]).toEqual([1,0,0,0,2,0]);
});
it('a missing beam does not claim visible space across its gap',()=>{
 const result=scanArea(new Float32Array([0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,-1,0,0]),3);
 expect(result.triangles).toHaveLength(0);expect(result.hits).toHaveLength(6);
});
