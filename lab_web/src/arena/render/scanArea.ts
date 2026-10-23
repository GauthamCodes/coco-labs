// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** A drawing fan of the measured beam endpoints; invalid beams never bridge a gap. */
export function scanArea(segments:Float32Array,maximum:number){
 const triangles:number[]=[],hits:number[]=[];
 const count=segments.length/6;
 for(let i=0;i<count;i++){
  const k=i*6,x=segments[k+3],y=segments[k+4];
  const range=Math.hypot(x-segments[k],y-segments[k+1]);
  if(range>0&&range<maximum-1e-4)hits.push(x,y,0);
  if(i===0)continue;
  const p=k-6;
  const previous=Math.hypot(segments[p+3]-segments[p],segments[p+4]-segments[p+1]);
  if(range<=0||previous<=0)continue;
  triangles.push(segments[k],segments[k+1],0,segments[p+3],segments[p+4],0,x,y,0);
 }
 return {triangles:new Float32Array(triangles),hits:new Float32Array(hits)};
}
