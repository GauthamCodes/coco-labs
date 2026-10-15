// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { ArenaPlayPanel } from '../play/ArenaPlayPanel';
import { EvidenceBadge, ModeNav } from '../ui/ModeNav';
import { Compare } from './Compare';
import { Joystick } from './Joystick';
import { PerfOverlay } from './PerfOverlay';
import { type LayerVisibility } from './render/Renderer';
import { TIER_CHOICES, type TierChoice } from './render/quality';
import { rebind, resetBindings } from './controls';
import { Help } from './Help';
import { Hud } from './Hud';
import { Timeline } from './Timeline';
import { caption } from './lens/captions';
import { EventLog, LensBar, LensCharts, LensInspector } from './lens/panels';
import { DecideControls, LocaliseControls, MapControls, MoveControls } from './lens/controls';
import { MissionPanel } from './lens/mission';
import { LENS_BY_ID } from './lens/registry';
import { GapChips } from '../learn/gaps';
import type { ArenaSceneModel } from './sceneCore';

export function ArenaSceneView({ model }: { model: ArenaSceneModel }) {
  const {
    params, showPerf, recId, missionBack, playParam, playLevel, playOn,
    raceOn, raceNotice, gaps, cfgInitial, canvas, world, liveReady,
    mode, session, error, inspect, setInspect, picked, layers,
    lens, setLens, level, setLevel, focus, setFocus, lensOn,
    setLensOn, hover, planner, cmpPick, setCmpPick, cmpA, setCmpA,
    cmpB, setCmpB, compare, setCompare, runCard, setRunCard, share,
    replay, converted, runs, r, client, queue, log,
    occupancy, outline, lastTick, qualityNote, tierChoice, setTierChoice, tierNow,
    setTierNow, coarse, camera, latched, setLatched, latchedRef, helpOpen,
    setHelpOpen, bindings, setBindings, settings, fullWheel, takeOver, sendConfig,
    toggle, choosePlanner, onJoystick, chooseCamera, onTank, changeSetting, makeShare,
    tick, lensesAvailable, plan, res, evidence, note, stats,
    m2, showLive,
  } = model;
  return (
    <main className="arena" data-testid="arena">
      {/* a pane inside the Case Files comparison (embed=1) shows its badge, not the modes again */}
      {params.get('embed') === '1'
        ? <p className="embed-head"><EvidenceBadge evidence={evidence} /></p>
        : <ModeNav current={params.has('play') ? 'play' : params.has('casefile') || params.has('replay') || params.has('run') ? 'research' : params.has('mission') || params.has('lens') || params.has('compare') ? 'compare' : 'play'} evidence={evidence} />}
      {missionBack && <p className="mission-back"><a href={`${import.meta.env.BASE_URL}${missionBack}`} data-testid="mission-back">
        ← Back to the mission</a></p>}
      {raceNotice && <p role="status" className="arena-toast">{raceNotice}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {qualityNote && <p className="notice" role="status">{qualityNote}</p>}
      {helpOpen && (
        <Help bindings={bindings} settings={settings} coarse={coarse}
          onRebind={(a, code) => setBindings((b) => rebind(b, a, code))}
          onReset={() => setBindings(resetBindings())}
          onSetting={changeSetting} onClose={() => setHelpOpen(false)} />
      )}
      {playOn && <ArenaPlayPanel challenge={playParam!} levelId={playLevel!}
        live={playParam === 'map-the-arena' || raceOn ? client.current : null} liveReady={liveReady}
        lastTick={() => lastTick.current} shownTick={() => session?.shownTick?.tick ?? null} log={() => log.current}
        onGhost={(flag, ghost) => r.current?.setRace(flag, ghost)} />}
      <p className={`arena-banner ${mode}`} data-testid="arena-mode" data-mode={mode}>
        {mode === 'attract' && (liveReady
          ? 'A recorded demo (MODEL, made when this site was built). Click or tap the map to give COCO a goal — the live model takes over.'
          : 'A recorded demo (MODEL, made when this site was built) while the live model loads… Click or tap the map to take over.')}
        {mode === 'live' && (coarse
          ? 'Live model: coco_lab running in your browser. Tap the floor for a goal, drive with the joystick; STOP latches until you release it. Two fingers orbit and zoom.'
          : 'Live model: coco_lab running in your browser. Click a goal, drive with W A S D / arrows or the joystick; Space is a latched STOP (R releases it). H shows every control.')}
        {mode === 'replay' && `Shared run: ${replay.status}`}
        {mode === 'recording' && converted && (converted.evidence === 'STACK'
          ? `Recorded run (STACK): COCO driven by the full ROS 2 stack in Gazebo — ${converted.title}. The solid robot is where the stack believed it was (AMCL); the outline is ground truth.`
            + (converted.pose3d ? ' In 3D the robot\'s body is Gazebo\'s ground truth, with the height and tilt it recorded; the solid footprint is the belief.' : '')
          : `Glass-box trace (MODEL): ${converted.title}, computed by coco_lab. No world, no robot: the search alone.`)}
      </p>
      {mode === 'recording' && converted && converted.evidence === 'STACK' && !converted.pose3d && (
        <p className="chip planar" data-testid="planar-chip" title="This recording kept only x, y and heading: its height, roll and pitch were never recorded, so they are not drawn or guessed">
          planar recording · no height or tilt recorded
        </p>
      )}
      <LensBar lens={lens} level={level} focus={focus} available={lensesAvailable}
        onLens={setLens} onLevel={setLevel} onFocus={setFocus} />
      {/* M2.9: the measured gaps between this lens's model and the Stack */}
      <GapChips ids={LENS_BY_ID[lens].gaps} gaps={gaps} />
      {lens === 'localise' && <LocaliseControls send={sendConfig} live={mode === 'live'} initial={cfgInitial} />}
      {lens === 'map' && <MapControls send={sendConfig} live={mode === 'live'} initial={cfgInitial} />}
      {lens === 'move' && (converted?.headers?.some((h) => h.channel === 'coco.control.local.header.v1')
        ? <p className="lens-hint" data-testid="move-recorded">Recorded (STACK): Nav2's own candidates as it logged them and the trajectory it chose each cycle — nothing here is computed by the model.</p>
        : <MoveControls send={sendConfig} live={mode === 'live'} initial={cfgInitial} />)}
      {lens === 'decide' && <DecideControls send={sendConfig} live={mode === 'live'} initial={cfgInitial} />}
      {lens === 'decide' && session && <MissionPanel session={session} tick={tick?.tick ?? 0} />}
      {level !== 'watch' && session && (() => { const c = caption(lens, session.families, tick?.tick ?? 0);
        return c ? <p className="lens-caption" data-testid="lens-caption" role="status">{c}</p> : null; })()}
      <div className="arena-stage">
        <canvas ref={canvas} className="arena-canvas" data-testid="arena-canvas"
          aria-label="The arena: click or tap to give COCO a goal" />
        {!world && <p className="arena-loading" data-testid="arena-status">Loading…</p>}
        {world && mode === 'live' && (
          <Hud tick={tick} latched={latched} fullWheel={fullWheel.current} showBars={settings.bars} camera={camera} coarse={coarse}
            tank={settings.tank}
            onStop={() => { takeOver(); queue.current.push({ kind: 'stop' }); latchedRef.current = true; setLatched(true); }}
            assistsLocked={raceOn}
            onContext={() => { if (!raceOn && !latchedRef.current) { takeOver(); queue.current.push({ kind: 'grasp' }); } }}
            onCamera={() => chooseCamera('next')}
            onAutonomy={() => { if (!raceOn && !latchedRef.current) { takeOver(); queue.current.push({ kind: 'autonomy' }); } }}
            onTank={onTank} />
        )}
        {latched && coarse && (
          <button type="button" className="hud-release" onClick={() => { latchedRef.current = false; setLatched(false); }}
            data-testid="hud-release">Release STOP</button>
        )}
        {hover && <span className="hover-label" data-testid="hover-label" style={{ left: hover.x, top: hover.y }}>{hover.text}</span>}
      </div>
      {compare && world && occupancy.current && (
        <Compare state={compare} world={world} occupancy={occupancy.current} outline={outline.current} onClose={() => setCompare(null)} />
      )}
      {runCard && (
        <section className="run-card" data-testid="run-card" aria-label="Run finished">
          <b>Goal reached.</b> The heatmap shows the order {runCard.planner} expanded cells: dark first, bright last.
          <span data-testid="run-totals"> {Number(runCard.summary.expansions).toLocaleString()} expansions
            {runCard.summary.path_cost != null ? ` · path cost ${Number(runCard.summary.path_cost).toFixed(2)} · path length ${(Number(runCard.summary.path_length) * res).toFixed(2)} m` : ''}</span>
          <button type="button" className="seg-btn" onClick={() => setRunCard(null)}>OK</button>
        </section>
      )}
      {converted?.card && (
        <section className="run-card" data-testid="stack-results" aria-label="Measured in this recorded run">
          <b>Measured in this run</b> (STACK, docs/labs/LAB5_MOVE.md): <span>{converted.card}</span>
        </section>
      )}
      {converted?.evidence === 'STACK' && stats && !converted.card && (
        <section className="run-card" data-testid="stack-results" aria-label="Measured in this recorded run">
          <b>Measured in this run</b> (Phase 1C, docs/RESULTS.md):
          <span> {stats.result?.phase ?? '—'} after {typeof stats.duration_sim_s === 'number' ? stats.duration_sim_s.toFixed(1) : '—'} s sim time ·
            tracking error mean {m2(stats.tracking_error_m?.mean)}, p95 {m2(stats.tracking_error_m?.p95)} ·
            endpoint error {m2(stats.endpoint_error_m)} · belief gap mean {m2(stats.belief_gap_m?.mean)}</span>
        </section>
      )}
      <section className="arena-panels">
        <Timeline session={session} />
        {note && <p className="stack-note" data-testid="stack-note">{note}</p>}
        {showLive && <>
        <div className="arena-row" role="group" aria-label="Planner">
          {(world?.planners ?? []).map((p) => (
            <button key={p} type="button" className={p === planner ? 'seg-btn active' : 'seg-btn'}
              disabled={raceOn} aria-pressed={p === planner} data-testid={`planner-${p}`} onClick={() => choosePlanner(p)}>{p}</button>
          ))}
          <button type="button" className={inspect ? 'seg-btn active' : 'seg-btn'} aria-pressed={inspect}
            data-testid="inspect-toggle" onClick={() => setInspect((v) => !v)}>Inspect a cell</button>
        </div>
        <div className="arena-row" role="group" aria-label="Compare two planners">
          <span>Compare</span>
          <select value={cmpA} onChange={(e) => setCmpA(e.target.value)} data-testid="compare-a" aria-label="Planner A">
            {(world?.planners ?? []).map((p) => <option key={p}>{p}</option>)}</select>
          <span>with</span>
          <select value={cmpB} onChange={(e) => setCmpB(e.target.value)} data-testid="compare-b" aria-label="Planner B">
            {(world?.planners ?? []).map((p) => <option key={p}>{p}</option>)}</select>
          <button type="button" className={cmpPick ? 'seg-btn active' : 'seg-btn'} data-testid="compare-pick"
            onClick={() => setCmpPick((v) => !v)}>{cmpPick ? 'Click the map for the goal…' : 'Pick a goal to compare'}</button>
        </div>
        </>}
        {!showLive && (
          <div className="arena-row">
            <button type="button" className={inspect ? 'seg-btn active' : 'seg-btn'} aria-pressed={inspect}
              data-testid="inspect-toggle" onClick={() => setInspect((v) => !v)}>Inspect a cell</button>
            <a href={`${import.meta.env.BASE_URL}?view=arena`}>Back to the live arena</a>
          </div>
        )}
        <div className="arena-row">
          {showLive && <Joystick onChange={onJoystick} />}
          <div className="layers-and-share">
            {lens !== 'plan' && (
              <div className="arena-row" role="group" aria-label={`${LENS_BY_ID[lens].title} layers`}>
                {LENS_BY_ID[lens].layers.map((x) => (
                  <label key={x.id} className="layer-toggle" title={x.meaning}><input type="checkbox" checked={lensOn[x.id] ?? false}
                    onChange={() => setLensOn((o) => ({ ...o, [x.id]: !o[x.id] }))} data-testid={`lens-layer-${x.id}`} data-role={x.role} />{x.label}</label>
                ))}
              </div>
            )}
            {tierNow && (
              <div className="arena-row">
                <label className="layer-toggle">3D quality{' '}
                  <select value={tierChoice} data-testid="quality-tier" onChange={(e) => {
                    const c = e.target.value as TierChoice;
                    setTierChoice(c);
                    r.current?.setTier(c);
                    setTierNow(r.current?.quality?.tier ?? null);
                  }}>
                    {TIER_CHOICES.map((t) => <option key={t} value={t}>{t === 'auto' ? `auto (now ${tierNow})` : t}</option>)}
                  </select>
                </label>
                <label className="layer-toggle" title="Walls, columns and landmarks stop at 0.35 m, so every layer stays in view">
                  <input type="checkbox" data-testid="low-walls" onChange={(e) => { if (r.current?.three) r.current.three.lowWalls = e.target.checked; }} />
                  low walls
                </label>
              </div>
            )}
            <div className="arena-row" role="group" aria-label="Layers">
              {(Object.keys(layers) as (keyof LayerVisibility)[]).map((k) => (
                <label key={k} className="layer-toggle"><input type="checkbox" checked={layers[k]} onChange={() => toggle(k)}
                  data-testid={`layer-${k}`} />{k}</label>
              ))}
            </div>
            {mode === 'live' && (
              <div className="arena-row">
                <button type="button" className="seg-btn" data-testid="help-open" onClick={() => setHelpOpen(true)}>Controls (H)</button>
                <button type="button" className="seg-btn" data-testid="share-make" onClick={makeShare}>Share this run</button>
                {share && <input className="share-url" readOnly value={share} data-testid="share-url" onFocus={(e) => e.target.select()} />}
              </div>
            )}
          </div>
        </div>
        {runs.length > 0 && (
          <nav className="arena-row recorded-runs" aria-label="Recorded and computed runs in this viewer" data-testid="recorded-runs">
            <span>Runs in this viewer:</span>
            {runs.map((x) => (
              <a key={x.id} href={`${import.meta.env.BASE_URL}?view=arena&replay=${x.id}`} data-testid={`replay-${x.id}`}
                aria-current={x.id === recId ? 'page' : undefined}>{x.evidence === 'STACK' ? `${x.title} · STACK` : x.title}</a>
            ))}
          </nav>
        )}
        <p data-testid="arena-tick">
          {world ? `tick ${tick?.tick ?? 0} · t = ${(tick?.t_world ?? 0).toFixed(1)} s · ${tick?.mode ?? 'idle'}` : ''}
          {plan ? ` · ${plan.planner}: ${plan.status}, ${plan.summary.expansions} expansions` +
            (plan.summary.path_cost != null ? `, path cost ${Number(plan.summary.path_cost).toFixed(2)}` : '') : ''}
        </p>
        {picked && (
          <dl className="inspector" data-testid="inspector">
            <dt>cell</dt><dd>({picked.row}, {picked.col}) · {picked.state}</dd>
            <dt>expansion order</dt><dd data-testid="inspector-order">{picked.expansion ?? '—'}</dd>
            <dt>g</dt><dd data-testid="inspector-g">{picked.g?.toFixed(3) ?? '—'}</dd>
            <dt>h</dt><dd>{picked.h?.toFixed(3) ?? '—'}</dd>
            <dt>f</dt><dd>{picked.f?.toFixed(3) ?? '—'}</dd>
            <dt>parent</dt><dd>{picked.parent ? `(${picked.parent[0]}, ${picked.parent[1]})` : '—'}</dd>
            <dt>latest event</dt><dd>{picked.event != null ? `#${picked.event} ${picked.kind}` : '—'}</dd>
          </dl>
        )}
        {level === 'inspect' && session && (
          <section className="lens-inspect" data-testid="lens-inspect" aria-label={`${LENS_BY_ID[lens].title} lens, Inspect`}>
            <LensInspector lens={LENS_BY_ID[lens]} store={session.families} tick={tick?.tick ?? 0} />
            <EventLog lens={LENS_BY_ID[lens]} store={session.families} tick={tick?.tick ?? 0} />
            <LensCharts lens={LENS_BY_ID[lens]} store={session.families} tick={tick?.tick ?? 0} />
          </section>
        )}
      </section>
      {showPerf && <PerfOverlay />}
    </main>
  );
}
