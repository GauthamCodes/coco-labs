// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {lazy,Suspense,useEffect,useState} from 'react';
import {SETTINGS_OPEN} from './settings_events';
const SettingsDrawer=lazy(()=>import('./SettingsDrawer'));
export function GlobalSettings(){
 const [open,setOpen]=useState(false);
 useEffect(()=>{const show=()=>setOpen(true);window.addEventListener(SETTINGS_OPEN,show);return()=>window.removeEventListener(SETTINGS_OPEN,show);},[]);
 return open?<Suspense fallback={null}><SettingsDrawer onClose={()=>setOpen(false)}/></Suspense>:null;
}
