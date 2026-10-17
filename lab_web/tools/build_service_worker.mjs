// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Hash the finished static site. Never discovers URLs from user requests. */
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { resolve, relative, join } from 'node:path';
import { fileURLToPath } from 'node:url';
export function buildServiceWorker(root, template) {
 const walk=dir=>readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?(e.name==='v1'?[]:walk(join(dir,e.name))):[join(dir,e.name)]);
 const files=walk(root).filter(p=>!['sw.js','cache-manifest.json','index.html'].includes(relative(root,p))&&!p.endsWith('.map')).sort();
 const assets=Object.fromEntries(files.map(p=>[relative(root,p).split('\\').join('/'),createHash('sha256').update(readFileSync(p)).digest('hex')]));
 const original=readFileSync(join(root,'index.html'),'utf8').replace(/<meta name="coco-build" content="[^"]*">/g,'');
 const version=createHash('sha256').update(JSON.stringify(assets)).update(original).update(template).digest('hex');
 writeFileSync(join(root,'index.html'),original.replace('</head>',`<meta name="coco-build" content="${version}"></head>`));
 assets['index.html']=createHash('sha256').update(readFileSync(join(root,'index.html'))).digest('hex');
 const critical=Object.keys(assets).filter(p=>p==='index.html'||p==='manifest.webmanifest'||p.startsWith('assets/')||p.startsWith('icons/')||p.startsWith('generated/pyodide/')||p.startsWith('generated/arena/')||p.startsWith('generated/py/')||p.startsWith('assets3d/')||(/^generated\/.*\.json$/.test(p))||p==='generated/casefiles/world.grid.bin');
 const manifest={version,assets,critical};
 writeFileSync(join(root,'cache-manifest.json'),JSON.stringify(manifest,null,1)+'\n');
 writeFileSync(join(root,'sw.js'),template.replace('/*__COCO_MANIFEST__*/',JSON.stringify(manifest)));
 return manifest;
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 const web=resolve(fileURLToPath(new URL('..',import.meta.url))),root=resolve(process.argv[2]??join(web,'dist'));
 const result=buildServiceWorker(root,readFileSync(join(web,'src/offline/sw.template.js'),'utf8'));console.log(`Static cache ${result.version}: ${result.critical.length} precached, ${Object.keys(result.assets).length} allowlisted`);
}
