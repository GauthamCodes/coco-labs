// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';
import { buildLibrary, filterLibrary, recordedOutcome, type CaseEntry } from '../src/research/library';
const file=(text:string,voided=false):CaseEntry=>({id:'one',title:'Hairpin',bytes:1,void:voided,compare:'',metadata:{controller:'DWB'},facts:[{text,evidence:['docs/RESULTS.md']}]});
describe('recordings library',()=>{
 it('keeps every distinct Case File and conversion, without collapsing shared sources',()=>{
  const rows=buildLibrary([{id:'move',title:'Move',lab:5,casefiles:[file('DWB: failed.'),file('DWB: failed.')]}],[{id:'one',title:'Converted',group:'Lab 5',algorithm:'DWB',evidence:'STACK',bytes:2,citation:'docs/RESULTS.md',outcome:'succeeded'}],'/lab/');
  expect(rows).toHaveLength(2);expect(rows.map(r=>r.kind)).toEqual(['casefile','converted']);expect(rows[0].href).toBe('/lab/?view=research&casefile=one');expect(rows[1].href).toBe('/lab/?view=research&replay=one');
  expect(filterLibrary(rows,{query:'hairpin dwb',level:'Lab 5',algorithm:'DWB',outcome:'failure',evidence:'STACK',failures:true})).toHaveLength(1);
 });
 it('does not invent outcomes from missing facts, titles or void recordings',()=>{expect(recordedOutcome(file(''))).toBe('not classified');expect(recordedOutcome(file('Not recovered in 181 s.'))).toBe('failure');expect(recordedOutcome(file('Recovered after 3 s.'))).toBe('success');expect(recordedOutcome(file('failed',true))).toBe('void');expect(recordedOutcome(file('DWB on static_room: follow_failed (error code 105).'))).toBe('failure');expect(recordedOutcome(file('Mission ABORT; home error 3 m.'))).toBe('failure')});
});
