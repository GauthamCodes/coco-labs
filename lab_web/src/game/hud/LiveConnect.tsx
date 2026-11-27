// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * R5.2: "Connect to ROS 2" -- the sheet where a visitor points Play at THEIR OWN coco-ros2 container.
 * The bridge URL (topics, read-only) and the control code (printed in the container's log) are all it
 * asks; the control gateway is the bridge's host on the next port. Nothing is stored or sent elsewhere.
 */
import { useState } from 'react';

export const DEFAULT_BRIDGE = 'ws://localhost:8765';
import { isLocalHost } from '../../ros/foxglove';
export const DOCKER_COMMAND = 'docker run --rm -p 8765:8765 -p 8766:8766 ghcr.io/gauthamcodes/coco-ros2 --level depot';

export interface LiveConnectProps {
  on: boolean; words: string; level: string;
  onConnect(url: string, code: string): void; onDisconnect(): void; onClose(): void;
}

export function LiveConnect(p: LiveConnectProps) {
  const [url, setUrl] = useState(DEFAULT_BRIDGE);
  const [code, setCode] = useState('');
  return <section className="g1-sheet g1-glass r5-live" role="dialog" aria-label="Connect to ROS 2" data-testid="r5-live-sheet">
    <h3>CONNECT TO ROS 2 <small>{p.on ? 'LIVE' : 'MODEL'}</small></h3>
    <p>Run COCO's real ROS 2 stack (Jazzy, Nav2, Gazebo, headless) on your computer, then connect. It is a simulation in
      Gazebo, labelled <b>LIVE</b> while it runs; no physical robot exists.</p>
    <pre className="r5-cmd" data-testid="r5-docker-command">{DOCKER_COMMAND}</pre>
    <p className="r5-note">This page is the {p.level}: start the container with the same level. When it is ready its log
      prints <code>CONTROL CODE: …</code>; enter it to drive. STOP always works, code or not.</p>
    {window.location.protocol === 'https:' && !isLocalHost(window.location.hostname) && <p className="r5-note" data-testid="r5-live-lna">Your browser may ask whether
      this site may connect to devices on your local network: choose <b>Allow</b>. Chrome and Firefox ask before a website can reach
      localhost, where the container runs.</p>}
    {!p.on && <form onSubmit={(e) => { e.preventDefault(); p.onConnect(url, code.trim()); }}>
      <label>Bridge URL <input data-testid="r5-live-url" value={url} onChange={(e) => setUrl(e.target.value)} spellCheck={false} autoComplete="off" /></label>
      <label>Control code <input data-testid="r5-live-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="8 characters" spellCheck={false} autoComplete="off" /></label>
      <button type="submit" className="main" data-testid="r5-live-connect">Connect</button>
    </form>}
    {p.on && <button className="main" data-testid="r5-live-disconnect" onClick={p.onDisconnect}>Disconnect (back to MODEL)</button>}
    {p.words && <p role="status" data-testid="r5-live-status">{p.words}</p>}
    <button className="x" aria-label="Close" onClick={p.onClose}>✕</button>
  </section>;
}
