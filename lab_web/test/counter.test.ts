// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { expect, it, vi } from 'vitest';
import { countVisit, counterEndpoint } from '../src/offline/counter';
it('empty counter has no network, storage, cookies or identity work',()=>{const send=vi.fn();countVisit('',send);expect(send).not.toHaveBeenCalled();expect(counterEndpoint('javascript:alert(1)')).toBeNull();expect(counterEndpoint('https://user:secret@example.test/count')).toBeNull()});
it('configured counter emits one empty anonymous increment, without the visitor URL',()=>{const send=vi.fn().mockResolvedValue(new Response());countVisit('https://counter.example.test/public/my-counter',send);expect(send).toHaveBeenCalledExactlyOnceWith('https://counter.example.test/public/my-counter',{method:'POST',body:'',credentials:'omit',referrerPolicy:'no-referrer',cache:'no-store',redirect:'error',keepalive:true})});
