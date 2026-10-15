// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { useEffect } from 'react';
import { ArrowUpRight, Columns2, Library, Navigation2 } from 'lucide-react';
import { WorldStage } from '../ui/reference/WorldStage';
import { warmModel } from '../arena/worker_pool';
import { navigate } from '../ui/navigation';
import '../ui/reference/reference.css';
const BASE = import.meta.env.BASE_URL;
export function TitleScreen() {
  useEffect(() => {
    let started = false;
    const play = (event: KeyboardEvent) => {
      if (started || event.repeat || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || ['Tab', 'Shift', 'Escape', 'Control', 'Alt', 'Meta'].includes(event.key)) return;
      if ((event.target as HTMLElement)?.closest('a,button,input,select,textarea,dialog')) return;
      started = true; event.preventDefault();
      navigate(`${BASE}?view=play`);
    };
    window.addEventListener('keydown', play); return () => window.removeEventListener('keydown', play);
  }, []);
  const cards = [{ label:'Play', copy:'Drive COCO. Race the planner.', icon:Navigation2, view:'play' }, { label:'Compare', copy:'One map. Different decisions.', icon:Columns2, view:'compare' }, { label:'Research', copy:'Explore recorded ROS 2 runs.', icon:Library, view:'research' }];
  return <main className="night-title" data-testid="title">
    <div className="night-title-world"><WorldStage kind="title" onReady={warmModel} /></div>
    <header className="night-title-header"><span className="night-eyebrow">THE NIGHT SHIFT</span><a href={`${BASE}?view=about`}>About <ArrowUpRight size={16}/></a></header>
    <div className="night-title-copy"><p className="night-eyebrow">A GLASS-BOX ROBOT LAB</p><h1>COCO <span>Lab</span></h1><p className="night-tagline">See what the robot computes.</p><span className="night-rule"/></div>
    <nav className="night-doors" aria-label="Choose a mode">{cards.map(({label,copy,icon:Icon,view})=><a className="night-door" key={view} href={`${BASE}?view=${view}`}><div className="night-door-top"><Icon size={24} strokeWidth={1.5}/><ArrowUpRight size={20}/></div><h2>{label}</h2><p>{copy}</p></a>)}</nav>
    <footer className="night-title-footer"><span>Press any key to play</span><span className="night-badge">MODEL <span>· kinematic</span></span></footer>
  </main>;
}
