// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {execFileSync} from 'node:child_process';
import {readFileSync,writeFileSync} from 'node:fs';
import {inflateRawSync} from 'node:zlib';
const files=execFileSync('git',['ls-files','docs','lab_web/test']).toString().trim().split('\n').filter(f=>/\.(json|md)$/.test(f));
const peaks={encoded:0,json:0,ticks:0,inputs:0,first_tick:0,id:0},from={};let count=0;
const seen=new Set();const links=[];
function peak(k,n,f){if(Number.isFinite(n)&&n>peaks[k]){peaks[k]=n;from[k]=f;}}
function strings(v){if(typeof v==='string')return[v];if(Array.isArray(v))return v.flatMap(strings);if(v&&typeof v==='object')return Object.values(v).flatMap(strings);return[];}
for(const f of files){const raw=readFileSync(f,'utf8');let text;
 try{text=f.endsWith('.json')?strings(JSON.parse(raw)):[raw];}catch{continue;}
 for(const s of text)for(const m of s.matchAll(/(?:https?:\/\/[^\s"<>]*?)?\?view=(?:arena|play)[^\s"<>]+/g)){
  const q=new URL(m[0],'https://x/').searchParams;
  for(const k of ['c','l','replay','casefile','play','pl'])peak('id',(q.get(k)||'').length,f);
  const field=q.has('z')?'z':q.has('s')?'s':q.has('run')?'run':null;if(!field)continue;
  try{const val=q.get(field),b=Buffer.from(val,'base64url'),bytes=field==='z'?inflateRawSync(b):b,d=JSON.parse(bytes);
   if(d.v!==1||!(d.h||d.c))continue;count++;peak('encoded',val.length,f);peak('json',bytes.length,f);
   const i=field==='run'?d.i:Array.isArray(d.i)?d.i:d.i?.log||[];
   peak('inputs',i.length,f);peak('ticks',d.t??d.i?.ticks??0,f);
   const t=i.map(r=>field==='run'?r[0]:r?.tick).filter(Number.isSafeInteger);
   if(t.length){peak('ticks',Math.max(...t),f);peak('first_tick',t[0],f);}
   const key=JSON.stringify({c:q.get('c'),l:q.get('l'),d});if(!seen.has(key)){seen.add(key);links.push({link:m[0],file:f});}
  }catch{}
 }
}
writeFileSync(process.argv[2]||'../docs/v2/data/m5/defects/link-corpus-v2.json',JSON.stringify({method:'JSON strings decoded before URL extraction; valid payloads, duplicate occurrences counted',count,peaks,from,margin:10,unique:links.length,links},null,1)+'\n');
console.log(JSON.stringify({count,peaks,from,unique:links.length}));
