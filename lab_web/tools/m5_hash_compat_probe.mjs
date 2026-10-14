// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import{readFileSync,writeFileSync}from'node:fs';
import{resolve}from'node:path';
import{execFileSync}from'node:child_process';
import{loadPyodide}from'pyodide';
import{decodeLink}from'./verify.mjs';
const src=JSON.parse(readFileSync('../docs/v2/data/m5/defects/committed-play-links.json'));
const after=JSON.parse(readFileSync('../docs/v2/data/m5/defects/committed-play-verified.json'));
const bad=after.rows.map((r,i)=>({r,i})).filter(x=>x.r.matches===false||x.r.error);
const py=await loadPyodide({indexURL:resolve('node_modules/pyodide')+'/',stdLibURL:resolve('public/generated/pyodide/python_stdlib.zip')});
const tar=execFileSync('git',['archive','c11bf9e','coco_lab/coco_lab']);
const zipScript=`import io,sys,tarfile,zipfile
class UTF8Info(zipfile.ZipInfo):
 def _encodeFilenameFlags(self): return self.filename.encode('utf-8'),self.flag_bits|0x800
out=io.BytesIO()
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read())) as t,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for m in sorted(t.getmembers(),key=lambda m:m.name):
  if not m.isfile() or not m.name.endswith('.py'):continue
  i=UTF8Info(m.name.removeprefix('coco_lab/'));i.compress_type=zipfile.ZIP_DEFLATED
  z.writestr(i,t.extractfile(m).read())
sys.stdout.buffer.write(out.getvalue())`;
const archive=execFileSync('python3',['-c',zipScript],{input:tar,maxBuffer:16*1024*1024});
py.unpackArchive(new Uint8Array(archive),'zip',{extractDir:'/home/pyodide'});
py.globals.set('L',readFileSync('play/levels.json','utf8'));py.globals.set('S',readFileSync('../worlds/coco_arena_v1.json','utf8'));
py.runPython("import sys,json,hashlib\nsys.path.insert(0,'/home/pyodide')\nfrom coco_lab import play\nlevels=json.loads(L)\nspec=json.loads(S)\ndef probe(s):\n r=play.score(levels,json.loads(s),spec)\n h=r.pop('hash')\n old=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()\n return json.dumps({'hash':h,'legacy_hash':old})");
const score=py.runPython('probe');
const rows=bad.map(({r,i})=>{const d=decodeLink(src.links[i]);const before=JSON.parse(score(JSON.stringify(d.submission)));return{source:src.sources[i],challenge:r.challenge,level:r.level,expected:r.expected,before_M5:before.hash,after_M5:r.hash,baseline_matches:before.hash===r.expected,M5_changed:before.hash!==r.hash,legacy_hash:before.legacy_hash,legacy_matches:before.legacy_hash===r.expected};});
writeFileSync('../docs/v2/data/m5/defects/v1-mismatch-baseline.json',JSON.stringify({baseline_sha:'c11bf9e',engine:'Pyodide '+py.version,rows},null,2)+'\n');
console.log(JSON.stringify(rows));
