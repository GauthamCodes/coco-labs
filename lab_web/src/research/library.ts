// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** A searchable index of static evidence; no recording is fetched for filtering. */
export interface Fact { text: string; evidence: string[] }
export interface Recording { id: string; title: string; kind: 'casefile' | 'converted'; level: string; algorithm: string; outcome: string; evidence: string; href: string; context?: string; facts: Fact[]; bytes: number }
export interface CaseEntry { id: string; title: string; bytes: number; void: boolean; compare: string; facts: Fact[]; metadata?: Record<string, unknown> }
export interface CaseGroup { id: string; title: string; lab: number; casefiles: CaseEntry[] }
export interface Converted { id: string; title: string; group: string; algorithm: string; evidence: string; bytes: number; citation: string; outcome?: string; level?: string }
export function recordedOutcome(file: CaseEntry): string {
 if(file.void)return 'void';
 const text=file.facts.map(f=>f.text).join(' ');
 if(/not recovered|did not find|follow_failed|Mission ABORT|\bfailed\b|\baborted\b|\btimed.out\b|\btimeout\b/i.test(text))return 'failure';
 if(/\bsucceeded\b|\bcompleted\b|Mission COMPLETE|\bRecovered after\b/i.test(text))return 'success';
 return 'not classified';
}
export const isFailure=(row:Recording)=>['failure','no_path','failed','aborted','timeout','timed_out','not_recovered','follow_failed','abort'].includes(row.outcome.toLowerCase());
export function buildLibrary(groups: CaseGroup[], converted: Converted[], base: string): Recording[] {
 const seen=new Set<string>(),rows:Recording[]=[];
 for(const group of groups)for(const file of group.casefiles){
  if(seen.has(file.id))continue;seen.add(file.id);
  const meta=file.metadata??{};
  rows.push({id:file.id,title:file.title,kind:'casefile',level:`Lab ${group.lab}`,algorithm:String(meta.controller??meta.algorithm??meta.backend??(group.lab===1&&typeof meta.run==='string'?meta.run.replace(/^run_/, ''):group.id==='lab2-kidnap'?'AMCL':'not recorded')),outcome:recordedOutcome(file),evidence:'STACK',href:`${base}?view=research&casefile=${encodeURIComponent(file.id)}`,context:`${base}?view=research&case=${encodeURIComponent(group.id)}&file=${encodeURIComponent(file.id)}`,facts:file.facts,bytes:file.bytes});
 }
 // These are distinct conversions, even where their source recording also has a Case File.
 for(const run of converted)rows.push({id:run.id,title:run.title,kind:'converted',level:run.level??run.group,algorithm:run.algorithm,outcome:run.outcome??'not classified',evidence:run.evidence,href:`${base}?view=research&replay=${encodeURIComponent(run.id)}`,facts:[{text:'Converted run; original source and round-trip validation.',evidence:[run.citation]}],bytes:run.bytes});
 return rows;
}
export interface Filters { query: string; level: string; algorithm: string; outcome: string; evidence: string; failures: boolean }
export function filterLibrary(rows: Recording[], f: Filters): Recording[] {
 const terms=f.query.toLowerCase().trim().split(/\s+/).filter(Boolean);
 return rows.filter(row=>terms.every(term=>[row.title,row.id,row.level,row.algorithm,row.outcome,row.evidence,...row.facts.map(x=>x.text)].join(' ').toLowerCase().includes(term))&&(!f.level||row.level===f.level)&&(!f.algorithm||row.algorithm===f.algorithm)&&(!f.outcome||row.outcome===f.outcome)&&(!f.evidence||row.evidence===f.evidence)&&(!f.failures||isFailure(row)));
}
