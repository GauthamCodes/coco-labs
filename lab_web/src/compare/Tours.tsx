// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { useEffect, useState } from 'react';
import stories from '../../tours/stories.json';
import { LearnApp, evidenceHref } from '../learn/LearnApp';
export interface TourPreset { id: string; family: 'global' | 'control' | 'localise'; names: string[]; radius?: number; lens?: string }
export function Tours({ onPreset }: { onPreset: (preset: TourPreset) => void }) {
  const [story, setStory] = useState(() => new URLSearchParams(location.search).get('tour') ?? '');
  const selected = stories.find(item => item.id === story);
  useEffect(() => { if (selected) onPreset({ ...selected, family: selected.family as TourPreset['family'] }); }, [selected?.id]);
  useEffect(() => { const back = () => setStory(new URLSearchParams(location.search).get('tour') ?? ''); window.addEventListener('popstate', back); return () => window.removeEventListener('popstate', back); }, []);
  const go = (id: string) => { const url = new URL(location.href); url.searchParams.set('tour', id); url.searchParams.delete('mission'); history.pushState(null, '', url); setStory(id); };
  return <section className="compare-tours" aria-label="Guided tours">
    <h2>Guided tours</h2>
    {selected ? <article data-testid="story-tour"><button onClick={() => go('')}>All tours</button><h3>{selected.title}</h3>{selected.claims.map((claim, i) => <p key={i}>{claim.text} {claim.evidence.map(ref => <a key={ref} className="cite" href={evidenceHref(ref)}>{ref}</a>)}</p>)}</article> : <>
      <h3>From the recorded Stack</h3><ul>{stories.map(item => <li key={item.id}><button onClick={() => go(item.id)}>{item.title}</button></li>)}</ul>
      <LearnApp embedded onPreset={(id, lens) => onPreset({ id, lens, family: lens === 'move' ? 'control' : lens === 'localise' ? 'localise' : 'global', names: lens === 'move' ? ['dwa', 'rpp'] : lens === 'localise' ? ['mcl', 'mcl_augmented'] : id === 'world-changes' ? ['astar', 'dstar_lite'] : ['astar', 'dijkstra'] })} />
    </>}
  </section>;
}
