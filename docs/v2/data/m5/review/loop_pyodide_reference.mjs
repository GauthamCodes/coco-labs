// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {loadPyodide} from '../../../../../lab_web/node_modules/pyodide/pyodide.mjs';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
import {gunzipSync} from 'node:zlib';
import {isDeepStrictEqual} from 'node:util';
import {conditions} from '../../../../../lab_web/tools/perf/conditions.mjs';
const start=conditions(),out=process.argv[2],web=fileURLToPath(new URL('../../../../../lab_web/',import.meta.url)),gen=join(web,'public/generated');
const py=await loadPyodide({indexURL:join(web,'node_modules/pyodide/'),stdLibURL:join(gen,'pyodide/python_stdlib.zip')});
py.unpackArchive(new Uint8Array(readFileSync(join(gen,'arena/coco_lab.zip'))),'zip',{extractDir:'/home/pyodide'});
py.FS.writeFile('/home/pyodide/arena_glue.py',readFileSync(join(web,'src/arena/arena_glue.py'),'utf8'));
py.runPython("import sys\nsys.path.insert(0,'/home/pyodide')\nimport arena_glue, json");
const mf=JSON.parse(readFileSync(join(gen,'arena/manifest.json'),'utf8')),loaded=new Set();
function pack(name){if(loaded.has(name))return;const p=mf.packs[name];for(const r of p.requires)pack(r);py.unpackArchive(new Uint8Array(readFileSync(join(gen,'arena',p.file))),'zip',{extractDir:'/home/pyodide'});py.runPython(`import importlib\nfor m in ${JSON.stringify(p.modules)}: importlib.import_module('coco_lab.'+m)`);loaded.add(name);}
pack('compare');py.globals.set('spec_json',readFileSync(join(gen,'arena/coco_arena_v1.json'),'utf8'));
const clean=v=>Array.isArray(v)?v.map(clean):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).filter(([k])=>k!=='compute_ms').map(([k,x])=>[k,clean(x)])):v;
const report={engine:`headless coco_lab, Pyodide ${py.version}, Node ${process.version}`,python:py.runPython('sys.version'),cases:[]};
for(const name of ['control','localise']){
 const data=JSON.parse(existsSync(join(out,`compare-${name}-events.json`))?readFileSync(join(out,`compare-${name}-events.json`),'utf8'):gunzipSync(readFileSync(join(out,`compare-${name}-events.json.gz`))).toString()),w=data.workers.filter(w=>w.sent.some(r=>r.type==='compare_loop')).at(-1),req=w.sent.filter(r=>r.type==='compare_loop').at(-1);
 const batches=w.messages.filter(r=>r.type==='compare_loop_batch');const last=batches.findLastIndex(r=>r.done),prev=batches.slice(0,last).findLastIndex(r=>r.done),actual=clean(batches.slice(prev+1,last+1).flatMap(b=>b.frames));
 py.runPython("arena_glue.init(spec_json,1,'astar',lambda *a:None,hash_version=2)");py.globals.set('request_json',JSON.stringify(req));py.runPython('arena_glue.loop_compare_begin(request_json)');
 const expected=[];for(let i=0;i<req.steps;i++)expected.push(clean(JSON.parse(py.runPython('arena_glue.loop_compare_advance()'))));
 const panes=req.names.map((algorithm,i)=>({pane:'ABCD'[i],algorithm,ticks:actual.length,exact:actual.length===expected.length&&actual.every((frames,j)=>isDeepStrictEqual(frames[i],expected[j][i]))}));
 report.cases.push({name,panes,excluded:'wall-clock compute_ms only',passed:panes.every(p=>p.exact)});
}
report.passed=report.cases.every(c=>c.passed);report.conditions={start,end:conditions()};writeFileSync(join(out,'loop-pyodide-reference.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));process.exitCode=report.passed?0:1;
