// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/* Static files only. No URL from a visitor is ever added to the allowlist. */
const manifest=/*__COCO_MANIFEST__*/;
const BASE=new URL('./',self.location.href),INDEX=new URL('index.html',BASE).href;
const PREFIX='coco-static-'+encodeURIComponent(BASE.pathname)+'-',NAME=PREFIX+manifest.version;
let bypassOldUnhashed=false;
const key=path=>new URL(path+'?__coco_asset='+manifest.assets[path],BASE).href;
const get=path=>fetch(new URL(path,BASE),{credentials:'omit',cache:'no-store'});
async function remember(cache,path,response,required=false){if(response.ok&&response.type!=='opaque'){const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await response.clone().arrayBuffer())),b=>b.toString(16).padStart(2,'0')).join('');if(digest!==manifest.assets[path]){if(required)throw Error('Precache content changed: '+path);return response}await cache.put(key(path),response.clone())}return response}
self.addEventListener('install',event=>event.waitUntil((async()=>{
 const cache=await caches.open(NAME);let i=0;
 await Promise.all(Array.from({length:4},async()=>{while(i<manifest.critical.length){const path=manifest.critical[i++];const response=await get(path);if(!response.ok)throw Error('Precache refused '+path);await remember(cache,path,response,true)}}));
 await self.skipWaiting();
})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{for(const name of await caches.keys())if(name.startsWith(PREFIX)&&name!==NAME)await caches.delete(name);await self.clients.claim()})()));
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url);
 if(request.method!=='GET'||url.origin!==BASE.origin||!url.pathname.startsWith(BASE.pathname))return;
 const path=url.pathname.slice(BASE.pathname.length);
 if(request.mode==='navigate'&&(path===''||path==='index.html')){
  // Always fetch/cache the canonical static index, never personal query strings.
  event.respondWith((async()=>{const cache=await caches.open(NAME);try{const response=await fetch(INDEX,{credentials:'omit',cache:'no-store'});if(!response.ok)throw Error('Index unavailable');const html=await response.clone().text();const version=html.match(/name="coco-build" content="([^"]+)"/)?.[1];if(version&&version!==manifest.version){bypassOldUnhashed=true;void self.registration.update();return response}await remember(cache,'index.html',response);return response}catch(error){const saved=await cache.match(key('index.html'));if(saved)return saved;throw error}})());return;
 }
 // Even an allowlisted file with a visitor's query is never stored.
 if(url.search||!Object.prototype.hasOwnProperty.call(manifest.assets,path))return;
 event.respondWith((async()=>{
  if(bypassOldUnhashed&&!/^assets\/.*-[A-Za-z0-9_-]+\./.test(path))return get(path);
  const cache=await caches.open(NAME),saved=await cache.match(key(path));if(saved)return saved;return remember(cache,path,await get(path));
 })());
});
