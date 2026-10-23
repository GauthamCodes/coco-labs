// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/* Static files only. No URL from a visitor is ever added to the allowlist.
 *
 * G1.8, update isolation: an open page keeps the build it loaded. Every build has its own
 * cache (its precached files and its manifest); the worker records which build each page
 * is (from the index it served it, or the page's 'hello'), and answers that page's
 * requests -- and its workers', which name the build in their path (__b/<build>/...) --
 * from that build's cache. A newer worker never deletes a build's cache while a page of
 * that build is open; it tells pages a new build is ready and never reloads them. */
const manifest=/*__COCO_MANIFEST__*/;
const BASE=new URL('./',self.location.href),INDEX=new URL('index.html',BASE).href;
const SCOPE=encodeURIComponent(BASE.pathname),PREFIX='coco-build-'+SCOPE+'-',LEGACY='coco-static-'+SCOPE+'-';
const NAME=PREFIX+manifest.version,CLIENTS=PREFIX+'clients',MANIFEST_KEY=new URL('__coco_manifest__',BASE).href;
const PIN=/^__b\/([0-9a-f]{64})\/(.*)$/;
const keyFor=(m,path)=>new URL(path+'?__coco_asset='+m.assets[path],BASE).href;
const clientKey=id=>new URL('__coco_client__/'+encodeURIComponent(id),BASE).href;
const builds=new Map([[manifest.version,manifest]]),owners=new Map();
const get=path=>fetch(new URL(path,BASE),{credentials:'omit',cache:'no-store'});
const digest=async response=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await response.clone().arrayBuffer())),b=>b.toString(16).padStart(2,'0')).join('');
async function remember(cache,m,path,response,required=false){if(response.ok&&response.type!=='opaque'){if(await digest(response)!==m.assets[path]){if(required)throw Error('Precache content changed: '+path);return response}await cache.put(keyFor(m,path),response.clone())}return response}
/** A build's manifest, if its cache is complete (install writes the manifest last). */
async function manifestOf(version){
 if(builds.has(version))return builds.get(version);
 if(!await caches.has(PREFIX+version))return null;
 const saved=await(await caches.open(PREFIX+version)).match(MANIFEST_KEY);if(!saved)return null;
 const m=await saved.json();builds.set(version,m);return m;
}
async function setOwner(id,version){if(!id||!version)return;owners.set(id,version);await(await caches.open(CLIENTS)).put(clientKey(id),new Response(version))}
async function ownerOf(id){
 if(!id)return null;if(owners.has(id))return owners.get(id);
 const saved=await(await caches.open(CLIENTS)).match(clientKey(id));const version=saved?await saved.text():null;owners.set(id,version);return version;
}
/** Delete a build's cache only when no open page is of that build (and never this one's). */
async function prune(){
 const live=new Set((await self.clients.matchAll({includeUncontrolled:true,type:'all'})).map(c=>c.id));
 const store=await caches.open(CLIENTS),inUse=new Set([manifest.version]);
 for(const request of await store.keys()){const id=decodeURIComponent(new URL(request.url).pathname.split('/__coco_client__/')[1]??'');
  if(live.has(id))inUse.add(await(await store.match(request)).text());else{await store.delete(request);owners.delete(id)}}
 for(const name of await caches.keys()){
  if(name.startsWith(LEGACY)){await caches.delete(name);continue}
  if(!name.startsWith(PREFIX)||name===CLIENTS||inUse.has(name.slice(PREFIX.length)))continue;
  // an install still filling its cache has no manifest yet: leave it to finish
  if(await(await caches.open(name)).match(MANIFEST_KEY)){await caches.delete(name);builds.delete(name.slice(PREFIX.length))}
 }
}
async function announce(){for(const c of await self.clients.matchAll({type:'window',includeUncontrolled:true}))c.postMessage({type:'coco-build',version:manifest.version})}
self.addEventListener('message',event=>{
 if(event.data==='static-version'){event.ports[0]?.postMessage(manifest.version);return}
 if(event.data?.type==='hello'&&typeof event.data.build==='string'&&/^[0-9a-f]{64}$/.test(event.data.build)){
  event.waitUntil((async()=>{await setOwner(event.source?.id,event.data.build);await prune();event.ports[0]?.postMessage({version:manifest.version,pins:true,retained:!!await manifestOf(event.data.build)})})());
 }
});
self.addEventListener('install',event=>event.waitUntil((async()=>{
 // an earlier install that never finished (no manifest) is abandoned: only one installs at a time
 for(const name of await caches.keys())if(name.startsWith(PREFIX)&&name!==NAME&&name!==CLIENTS&&!await(await caches.open(name)).match(MANIFEST_KEY))await caches.delete(name);
 const cache=await caches.open(NAME);let i=0;
 await Promise.all(Array.from({length:4},async()=>{while(i<manifest.critical.length){const path=manifest.critical[i++];const response=await get(path);if(!response.ok)throw Error('Precache refused '+path);await remember(cache,manifest,path,response,true)}}));
 await cache.put(MANIFEST_KEY,new Response(JSON.stringify(manifest),{headers:{'Content-Type':'application/json'}}));
 await self.skipWaiting();
})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{await self.clients.claim();await prune();await announce()})()));
/** Answer `path` for a page of build `version`: from that build's cache, else the network if it still serves those bytes. */
async function serve(version,path,request){
 const m=await manifestOf(version);
 // not a file of that build (or a build this worker never cached): the network, as asked
 if(!m||!Object.prototype.hasOwnProperty.call(m.assets,path))return request?fetch(request):get(path);
 const cache=await caches.open(PREFIX+version),saved=await cache.match(keyFor(m,path));if(saved)return saved;
 const response=await get(path);
 if(version===manifest.version)return remember(cache,m,path,response);
 if(response.ok&&await digest(response)===m.assets[path]){await cache.put(keyFor(m,path),response.clone());return response}
 return new Response('This file belongs to an earlier build of COCO Lab that is no longer served. Reload to use the new version.',{status:410,headers:{'Content-Type':'text/plain'}});
}
/** Which build a request is for: its path's pin, its page's build, or the build whose files include it. */
async function buildFor(event,path){
 const owner=await ownerOf(event.clientId);if(owner)return owner;
 if(Object.prototype.hasOwnProperty.call(manifest.assets,path))return manifest.version;
 // content-hashed files (a worker's own chunks) are the same bytes in every build that has them
 for(const name of await caches.keys()){if(!name.startsWith(PREFIX)||name===CLIENTS)continue;const m=await manifestOf(name.slice(PREFIX.length));if(m&&Object.prototype.hasOwnProperty.call(m.assets,path))return m.version}
 return manifest.version;
}
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url);
 if(request.method!=='GET'||url.origin!==BASE.origin||!url.pathname.startsWith(BASE.pathname))return;
 const rel=url.pathname.slice(BASE.pathname.length),pin=rel.match(PIN);
 if(pin){event.respondWith(serve(pin[1],pin[2],null));return}
 const path=rel;
 if(request.mode==='navigate'&&(path===''||path==='index.html')){
  // Always fetch/cache the canonical static index, never personal query strings; the new
  // page is recorded as the build of the index it is given.
  event.respondWith((async()=>{const cache=await caches.open(NAME);try{const response=await fetch(INDEX,{credentials:'omit',cache:'no-store'});if(!response.ok)throw Error('Index unavailable');const html=await response.clone().text();const version=html.match(/name="coco-build" content="([^"]+)"/)?.[1];await setOwner(event.resultingClientId,version);if(version&&version!==manifest.version){void self.registration.update();return response}await remember(cache,manifest,'index.html',response);return response}catch(error){const saved=await cache.match(keyFor(manifest,'index.html'));if(saved){await setOwner(event.resultingClientId,manifest.version);return saved}throw error}})());return;
 }
 // Even an allowlisted file with a visitor's query is never stored.
 if(url.search)return;
 event.respondWith((async()=>serve(await buildFor(event,path),path,request))());
});
