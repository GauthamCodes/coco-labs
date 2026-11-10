// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R4: the course's diagrams -- one per Explain step, drawn here (no external assets). Colours are
 * the Okabe-Ito palette (safe for the common colour-vision deficiencies), and no diagram relies on
 * colour alone: every mark that differs in colour also differs in label, shape or dash. Text uses
 * currentColor so both themes work. Each SVG has a title and a description for screen readers.
 */
import type { ReactNode } from 'react';

const C = { orange: '#E69F00', sky: '#56B4E9', green: '#009E73', yellow: '#F0E442', blue: '#0072B2', red: '#D55E00', purple: '#CC79A7' };

function Fig({ id, title, desc, children, h = 200 }: { id: string; title: string; desc: string; children: ReactNode; h?: number }) {
  return (
    <figure className="course-diagram" data-testid={`diagram-${id}`}>
      <svg viewBox={`0 0 420 ${h}`} role="img" aria-labelledby={`d-${id}-t d-${id}-d`} width="100%" style={{ maxWidth: 520 }}>
        <title id={`d-${id}-t`}>{title}</title>
        <desc id={`d-${id}-d`}>{desc}</desc>
        <g fontFamily="inherit" fontSize="12" fill="currentColor">{children}</g>
      </svg>
      <figcaption>{title}</figcaption>
    </figure>
  );
}

function Grid({ x, y, n, m, s, fill }: { x: number; y: number; n: number; m: number; s: number; fill: (i: number, j: number) => string | null }) {
  const cells = [];
  for (let i = 0; i < n; i++) for (let j = 0; j < m; j++) {
    const f = fill(i, j);
    cells.push(<rect key={`${i}-${j}`} x={x + i * s} y={y + j * s} width={s} height={s} fill={f ?? 'none'} stroke="currentColor" strokeOpacity={0.25} />);
  }
  return <g>{cells}</g>;
}

function Search() {
  // Dijkstra's ripple (left) against A*'s lean (right); S start, G goal, numbers = expansion order rings
  const ring = (i: number, j: number, cx: number, cy: number) => Math.max(Math.abs(i - cx), Math.abs(j - cy));
  return (
    <Fig id="search" title="Dijkstra spreads in every direction; A* leans towards the goal" desc="Two 9 by 7 grids. Left, Dijkstra: shaded cells form a full ring around the start reaching the goal. Right, A*: only a narrow band of cells between start and goal is shaded. Both paths to the goal cost the same.">
      <Grid x={10} y={30} n={9} m={7} s={20} fill={(i, j) => (ring(i, j, 2, 3) <= 4 ? C.sky : null)} />
      <Grid x={220} y={30} n={9} m={7} s={20} fill={(i, j) => (Math.abs(j - 3) <= 1 && i >= 2 && i <= 6 ? C.sky : null)} />
      {[[10, 'Dijkstra'], [220, 'A*']].map(([x, t]) => (
        <g key={t as string}>
          <text x={(x as number) + 90} y={20} textAnchor="middle" fontWeight="bold">{t}</text>
          <text x={(x as number) + 50} y={94} textAnchor="middle" fontWeight="bold">S</text>
          <text x={(x as number) + 130} y={94} textAnchor="middle" fontWeight="bold">G</text>
          <line x1={(x as number) + 58} y1={90} x2={(x as number) + 122} y2={90} stroke={C.red} strokeWidth={3} />
        </g>
      ))}
      <text x={10} y={190}>Shaded = expanded cells. Same path cost (line); A* expands fewer.</text>
    </Fig>
  );
}

function Inflation() {
  const pts = [];
  for (let d = 0; d <= 60; d++) {
    const m = d / 100;
    const c = m === 0 ? 254 : m <= 0.22 ? 253 : m > 0.55 ? 0 : 252 * Math.exp(-10 * (m - 0.22));
    pts.push(`${40 + d * 5.5},${170 - c * 0.55}`);
  }
  return (
    <Fig id="inflation" title="Inflation: cost against distance from an obstacle" desc="A graph. Cost is 254 at distance 0, 253 up to the robot radius 0.22 m, then falls exponentially from 252 to near zero, and is 0 beyond the inflation radius 0.55 m.">
      <line x1={40} y1={170} x2={380} y2={170} stroke="currentColor" />
      <line x1={40} y1={20} x2={40} y2={170} stroke="currentColor" />
      <polyline points={pts.join(' ')} fill="none" stroke={C.blue} strokeWidth={3} />
      <line x1={40 + 22 * 5.5} y1={20} x2={40 + 22 * 5.5} y2={170} stroke={C.orange} strokeDasharray="4 3" />
      <line x1={40 + 55 * 5.5} y1={20} x2={40 + 55 * 5.5} y2={170} stroke={C.green} strokeDasharray="1 3" strokeWidth={2} />
      <text x={44} y={30}>254 lethal · 253 inscribed</text>
      <text x={40 + 22 * 5.5 + 4} y={60}>robot radius</text>
      <text x={40 + 55 * 5.5 + 4} y={90}>inflation radius</text>
      <text x={200} y={190} textAnchor="middle">distance to the nearest obstacle (m)</text>
      <text x={14} y={100} transform="rotate(-90 14 100)" textAnchor="middle">cost</text>
    </Fig>
  );
}

function Replan() {
  return (
    <Fig id="replan" title="The world changes: replan from scratch or repair" desc="A path from S to G is blocked by a new obstacle marked X. A dashed new path goes around it. Left label: A* searches again from scratch. Right label: D* Lite repairs the part the change affected.">
      <rect x={40} y={40} width={340} height={120} fill="none" stroke="currentColor" strokeOpacity={0.4} />
      <text x={50} y={104} fontWeight="bold">S</text><text x={360} y={104} fontWeight="bold">G</text>
      <line x1={64} y1={100} x2={354} y2={100} stroke={C.blue} strokeWidth={3} />
      <rect x={190} y={84} width={34} height={32} fill={C.red} />
      <text x={207} y={105} textAnchor="middle" fill="#000" fontWeight="bold">X</text>
      <polyline points="64,100 170,100 190,60 230,60 250,100 354,100" fill="none" stroke={C.green} strokeWidth={3} strokeDasharray="6 4" />
      <text x={40} y={182}>A*: search again from S. D* Lite: repair only what X changed.</text>
      <text x={40} y={30}>solid = old plan · dashed = new plan</text>
    </Fig>
  );
}

function Follow() {
  return (
    <Fig id="follow" title="Pure pursuit steers to a lookahead point; DWA and MPPI score candidates" desc="Left: a robot, a path bending left, a point one lookahead ahead on the path and the single arc to it. Right: the same robot with several fanned candidate arcs; the chosen one is thicker.">
      <circle cx={70} cy={150} r={10} fill="none" stroke="currentColor" strokeWidth={2} />
      <polyline points="70,150 70,80 150,40" fill="none" stroke={C.blue} strokeWidth={3} />
      <circle cx={95} cy={68} r={6} fill={C.orange} />
      <path d="M70 140 Q 72 90 95 68" fill="none" stroke={C.red} strokeWidth={2} strokeDasharray="5 3" />
      <text x={102} y={66}>lookahead point</text>
      <text x={20} y={190}>Pure pursuit: one arc</text>
      {[-50, -25, 0, 25, 50].map((a) => (
        <path key={a} d={`M300 150 Q ${300 + a / 2} 100 ${300 + a} 60`} fill="none" stroke={a === -25 ? C.green : 'currentColor'} strokeOpacity={a === -25 ? 1 : 0.45} strokeWidth={a === -25 ? 4 : 1.5} />
      ))}
      <circle cx={300} cy={150} r={10} fill="none" stroke="currentColor" strokeWidth={2} />
      <text x={230} y={190}>DWA / MPPI: score many, pick (thick)</text>
    </Fig>
  );
}

function Particles() {
  const pts: [number, number, number][] = [];
  let s = 7;
  const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 40; i++) pts.push([60 + r() * 120, 60 + r() * 90, 1]);
  for (let i = 0; i < 40; i++) pts.push([260 + (r() - 0.5) * 30, 100 + (r() - 0.5) * 30, 2]);
  return (
    <Fig id="particles" title="A particle filter: many guesses, resampled towards the good ones" desc="Left: particles spread widely, before a scan is matched. Right: after resampling, the particles cluster tightly around the true pose, marked by a ring.">
      {pts.map(([x, y, k], i) => <circle key={i} cx={x} cy={y} r={k === 1 ? 2.5 : 2} fill={k === 1 ? C.sky : C.blue} />)}
      <circle cx={260} cy={100} r={22} fill="none" stroke={C.red} strokeWidth={2} strokeDasharray="4 3" />
      <text x={60} y={180}>before: unsure (spread)</text>
      <text x={230} y={180}>after resampling: sure</text>
      <text x={290} y={70}>true pose</text>
      <text x={196} y={110} fontSize="20">→</text>
    </Fig>
  );
}

function LogOdds() {
  const steps = [0, 0.85, 0.45, 1.3, 2.15, 1.75];
  return (
    <Fig id="logodds" title="Log-odds: each hit adds, each pass subtracts, clamped" desc="A bar chart of one cell's log-odds over six observations: start 0, hit to 0.85, pass to 0.45, hit to 1.3, hit to 2.15, pass to 1.75. Dashed lines at plus and minus 4 mark the clamp.">
      <line x1={30} y1={100} x2={400} y2={100} stroke="currentColor" />
      <line x1={30} y1={20} x2={400} y2={20} stroke={C.red} strokeDasharray="4 3" /><text x={300} y={16}>clamp +4</text>
      <line x1={30} y1={180} x2={400} y2={180} stroke={C.red} strokeDasharray="4 3" /><text x={300} y={196}>clamp -4</text>
      {steps.map((v, i) => (
        <g key={i}>
          <rect x={45 + i * 58} y={v >= 0 ? 100 - v * 20 : 100} width={36} height={Math.abs(v) * 20 || 1} fill={i === 0 ? 'currentColor' : C.blue} fillOpacity={i === 0 ? 0.3 : 1} />
          <text x={63 + i * 58} y={v >= 0 ? 94 - v * 20 : 116} textAnchor="middle">{v.toFixed(2)}</text>
          <text x={63 + i * 58} y={140} textAnchor="middle">{['start', 'hit', 'pass', 'hit', 'hit', 'pass'][i]}</text>
        </g>
      ))}
    </Fig>
  );
}

function Arbiter() {
  const row = (y: number, t: string, f: string, k: string) => (
    <g key={t}><rect x={30} y={y} width={150} height={30} rx={6} fill={f} /><text x={105} y={y + 20} textAnchor="middle" fill="#000">{t}</text><text x={190} y={y + 20}>{k}</text></g>
  );
  return (
    <Fig id="arbiter" title="One node drives the wheels: STOP beats teleop beats autonomy" desc="Three boxes ranked top to bottom: STOP (rank 1), teleop (rank 2), autonomy and assists (rank 3). Arrows lead to one box, cmd_vel arbiter, then to the wheels.">
      {row(20, 'STOP (latched)', C.red, '1 · blocks drive until a mode is picked')}
      {row(70, 'teleop', C.orange, '2 · preempts every mode')}
      {row(120, 'autonomy, assists', C.sky, '3')}
      <rect x={30} y={168} width={360} height={26} rx={6} fill="none" stroke="currentColor" strokeWidth={2} />
      <text x={210} y={186} textAnchor="middle" fontWeight="bold">cmd_vel arbiter → the only wheel publisher</text>
    </Fig>
  );
}

function SearchBays() {
  const bays = [[60, 'Bay 1', '0.40'], [150, 'Bay 2', '0.25'], [240, 'Bay 3', '0.20'], [330, 'Bay 4', '0.15']] as const;
  return (
    <Fig id="search-bays" title="Where to look first: probability and distance together" desc="Four bays in a row with an example belief: bay 1 0.40, bay 2 0.25, bay 3 0.20, bay 4 0.15, and the robot below bay 3. The best order weighs how likely each bay is against how far it is.">
      {bays.map(([x, t, p]) => (
        <g key={t}><rect x={x - 35} y={30} width={70} height={60} fill="none" stroke="currentColor" />
          <rect x={x - 35} y={90 - Number(p) * 140} width={70} height={Number(p) * 140} fill={C.sky} fillOpacity={0.7} />
          <text x={x} y={22} textAnchor="middle">{t}</text><text x={x} y={110} textAnchor="middle">p = {p}</text></g>
      ))}
      <circle cx={240} cy={160} r={10} fill="none" stroke="currentColor" strokeWidth={2} /><text x={256} y={164}>robot</text>
      <text x={20} y={194}>Example belief only. Expected distance until found = what to minimise.</text>
    </Fig>
  );
}

function Timeline() {
  const pts = [];
  for (let t = 0; t <= 100; t++) pts.push(`${30 + t * 3.6},${t < 45 ? 150 - t * 2.4 : 42 + Math.sin(t) * 2}`);
  return (
    <Fig id="timeline" title="Reading a recording: the cause comes before the message" desc="A line of progress over time rises, then flattens at about 45 percent of the run. A marker labels the flat start 'stuck here'; a later marker at the end labels 'failure reported'.">
      <line x1={30} y1={170} x2={400} y2={170} stroke="currentColor" />
      <polyline points={pts.join(' ')} fill="none" stroke={C.blue} strokeWidth={3} />
      <line x1={30 + 45 * 3.6} y1={20} x2={30 + 45 * 3.6} y2={170} stroke={C.orange} strokeWidth={2} />
      <text x={30 + 45 * 3.6 + 4} y={30}>stuck here (the cause)</text>
      <line x1={390} y1={20} x2={390} y2={170} stroke={C.red} strokeDasharray="4 3" strokeWidth={2} />
      <text x={386} y={60} textAnchor="end">failure reported</text>
      <text x={200} y={190} textAnchor="middle">time (ticks) → · line = progress towards the goal</text>
    </Fig>
  );
}

function RosGraph() {
  const box = (x: number, y: number, w: number, t: string) => (
    <g key={t}><rect x={x} y={y} width={w} height={28} rx={6} fill="none" stroke="currentColor" strokeWidth={1.5} /><text x={x + w / 2} y={y + 18} textAnchor="middle">{t}</text></g>
  );
  return (
    <Fig id="ros-graph" title="ROS 2 nodes talk over topics; TF keeps map → odom → base_link" h={220} desc="Boxes for nodes: LiDAR, odometry, AMCL, costmap, planner server, controller server, cmd_vel arbiter. Labelled arrows are topics: /scan, /odom, the costmap_raw topic, /plan, /cmd_vel. A separate chain shows frames map to odom (published by AMCL) to base_link (published by odometry).">
      {box(10, 20, 80, 'LiDAR')}{box(10, 70, 80, 'odometry')}
      {box(140, 20, 90, 'AMCL')}{box(140, 70, 90, 'costmap')}
      {box(270, 70, 140, 'planner server')}{box(270, 120, 140, 'controller server')}{box(270, 170, 140, 'cmd_vel arbiter')}
      <g stroke={C.blue} strokeWidth={2} fill="none">
        <line x1={90} y1={34} x2={140} y2={34} /><line x1={90} y1={84} x2={140} y2={84} />
        <line x1={230} y1={84} x2={270} y2={84} /><line x1={340} y1={98} x2={340} y2={120} /><line x1={340} y1={148} x2={340} y2={170} />
      </g>
      <text x={96} y={28}>/scan</text><text x={96} y={78}>/odom</text><text x={232} y={78}>_raw</text>
      <text x={346} y={113}>/plan</text><text x={346} y={163}>/cmd_vel</text>
      <text x={10} y={140}>frames:</text>
      <text x={10} y={160}>map →(AMCL)→ odom</text><text x={10} y={180}>odom →(odometry)→ base_link</text>
    </Fig>
  );
}

export const DIAGRAMS: Record<string, () => ReactNode> = {
  search: Search, inflation: Inflation, replan: Replan, follow: Follow, particles: Particles,
  logodds: LogOdds, arbiter: Arbiter, 'search-bays': SearchBays, timeline: Timeline, 'ros-graph': RosGraph,
};

export function Diagram({ id }: { id: string }) {
  const D = DIAGRAMS[id];
  return D ? <D /> : null;
}
