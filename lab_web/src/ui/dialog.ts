// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import type {KeyboardEvent} from 'react';
/** Native dialogs can focus the document after their last control in some browsers. */
export function trapDialogTab(event:KeyboardEvent<HTMLDialogElement>){
 if(event.key!=='Tab'||event.ctrlKey||event.metaKey||event.altKey)return;
 const controls=[...event.currentTarget.querySelectorAll<HTMLElement>('button,input,select,a[href],summary,[tabindex]')].filter(element=>element.tabIndex>=0&&!element.hasAttribute('disabled')&&element.getClientRects().length>0);
 const index=controls.indexOf(document.activeElement as HTMLElement);
 if(event.shiftKey&&index<=0){event.preventDefault();controls.at(-1)?.focus();}
 else if(!event.shiftKey&&index===controls.length-1){event.preventDefault();controls[0]?.focus();}
}
