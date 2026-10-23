// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Optional enhancement: unsupported/blocked workers never prevent the app booting. */
export function registerStaticCache(){
 if(!import.meta.env.PROD||!('serviceWorker' in navigator))return;
 const run=()=>{void navigator.serviceWorker.register(import.meta.env.BASE_URL+'sw.js',{scope:import.meta.env.BASE_URL,updateViaCache:'none'}).then(r=>r.update()).catch(()=>{/* app still works without caching */})};
 // Let the first scene and interpreter use the connection before precaching other modes.
 if(navigator.serviceWorker.controller)run();else window.setTimeout(run,15000);
}
