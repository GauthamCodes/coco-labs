// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { loadPyodide } from 'pyodide';
import { readFileSync,writeFileSync } from 'node:fs';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();
const py=await loadPyodide({indexURL:'node_modules/pyodide/',stdLibURL:'public/generated/pyodide/python_stdlib.zip'});
const manifest=JSON.parse(readFileSync('public/generated/arena/manifest.json'));
for(const file of ['coco_lab.zip',...['localise','move','compare'].map(name=>manifest.packs[name].file)])py.unpackArchive(new Uint8Array(readFileSync('public/generated/arena/'+file)),'zip',{extractDir:'/home/pyodide'});
if(process.argv[3]==='source')py.FS.writeFile('/home/pyodide/coco_lab/state_v2.py',readFileSync('../coco_lab/coco_lab/state_v2.py','utf8'));
py.globals.set('spec_json',readFileSync('public/generated/arena/coco_arena_v1.json','utf8'));
const result=JSON.parse(py.runPython(`
import sys,json,time
sys.path.insert(0,'/home/pyodide')
from coco_lab.arena import Arena
from coco_lab.localise import MCL
from coco_lab.loc_arena import ArenaLocaliser
from coco_lab.compare_loop import LoopComparison
calls={}
for cls,name in [(Arena,'_scan'),(MCL,'update'),(ArenaLocaliser,'_start'),(Arena,'state_bytes')]:
    original=getattr(cls,name)
    key=cls.__name__+'.'+name
    def wrap(*args,_original=original,_key=key,**kwargs):
        t=time.perf_counter()
        result=_original(*args,**kwargs)
        calls[_key]=calls.get(_key,0)+(time.perf_counter()-t)*1000
        return result
    setattr(cls,name,wrap)
t=time.perf_counter()
c=LoopComparison(json.loads(spec_json),dict(family='localise',names=['mcl','mcl_augmented'],steps=2,goal=[2.5,2],inflation=dict(inflation_radius=.5,cost_scaling_factor=10,robot_radius=.25)))
construction_ms=(time.perf_counter()-t)*1000
rows=c.advance()
first=dict(calls)
rows=c.advance()
json.dumps(dict(construction_ms=construction_ms,first=first,total=calls,particles=len(rows[0]['particles'][0])))
`));
writeFileSync(process.argv[2]??'../docs/v2/data/m5/compare/pyodide-profile.json', JSON.stringify({ result, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n');
