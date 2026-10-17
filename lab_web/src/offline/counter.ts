// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** One aggregate increment per document; no cookies, fingerprint or visitor payload. */
export function counterEndpoint(id: string): string | null {
 if(!id)return null;
 try{const url=new URL(id);return url.protocol==='https:'&&!url.username&&!url.password&&!url.hash?url.href:null}catch{return null}
}
export function countVisit(id:string,send:typeof fetch=fetch):void{
 const endpoint=counterEndpoint(id);if(!endpoint)return;
 void send(endpoint,{method:'POST',body:'',credentials:'omit',referrerPolicy:'no-referrer',cache:'no-store',redirect:'error',keepalive:true}).catch(()=>{/* counter failure never changes the product */});
}
