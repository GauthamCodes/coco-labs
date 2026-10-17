// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { writeFileSync } from 'node:fs';
import { TOKENS } from '../src/ui/tokens.ts';
import { contrast, deltaE, simulate } from '../src/ui/colour_checks.ts';
import { conditions } from './perf/conditions.mjs';
const roles=['frontier','closed','path','rejected','particles','truth'];
const rows=[];
for(const theme of ['dark','light'])for(const kind of ['protanopia','deuteranopia']){
 const colours=Object.fromEntries(roles.map(role=>[role,simulate(TOKENS.computation[theme][role],kind)]));
 const pairs=roles.flatMap((a,i)=>roles.slice(i+1).map(b=>({a,b,deltaE:deltaE(colours[a],colours[b])}))).sort((a,b)=>a.deltaE-b.deltaE);
 rows.push({theme,kind,colours,pairs,minimum:pairs[0]});
}
const ui=Object.entries(TOKENS.colours).flatMap(([theme,p])=>['fg','muted','accent','recorded','browser','glass'].flatMap(role=>['bg','panel','panel2'].map(background=>({theme,role,background,ratio:contrast(p[role],p[background])}))));
writeFileSync(process.argv[2],JSON.stringify({conditions:conditions(),method:'Machado 2009 severity 100, linear RGB; opaque role swatches; CIELAB D65 deltaE76 >=10 is an engineering check, not a clinical/usability threshold',rows,ui},null,2)+'\n');
