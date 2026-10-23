// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { REPO_BLOB_URL } from '../../site.config';
import { ModeNav } from '../ui/ModeNav';
import './shell.css';
const BASE = import.meta.env.BASE_URL;
export function AboutPage() {
  return <main className="about-page" data-testid="about">
    <ModeNav current="about" evidence="MODEL"/>
    <h1>See what the robot computes.</h1>
    <p>COCO Lab is a glass-box robot lab. Drive COCO in Play, compare its algorithms side by side, or explore reproducible recordings in Research.</p>
    <p>The live browser model uses differential-drive kinematics. It shows decisions and geometry; it does not simulate wheel slip, tipping, friction or contact forces. COCO has two gripper fingers and a magnet; the magnet holds the object. No physical COCO robot exists.</p>
    <h2>What the evidence labels mean</h2>
    <dl>
      <dt>MODEL</dt><dd>The Python reference model, running in your browser. A simplified model, not a physical robot.</dd>
      <dt>STACK</dt><dd>The full ROS 2 stack in Gazebo, recorded on a laptop. A simulation, with its failures kept visible.</dd>
      <dt>REMOTE</dt><dd>That simulated stack, controlled over a network.</dd>
      <dt>EXTERNAL</dt><dd>A visitor's own ROS 2 system. This connection is planned for a later milestone.</dd>
      <dt>HARDWARE</dt><dd>A physical robot. There are no COCO hardware results.</dd>
      <dt>UNRESOLVED</dt><dd>A result that is unexplained, untested or statistically inconclusive.</dd>
      <dt>CONCEPT</dt><dd>An idea that has been discussed but not built.</dd>
    </dl>
    <p>MEASURED means a saved measurement; TESTED means a checked property. ASSUMPTION is a chosen value. INFERENCE is reasoning from evidence. Every teaching claim keeps its evidence link.</p>
    <h2>Explore</h2>
    <p><a href={`${BASE}?view=live`} data-testid="live-link">Live Stack (simulated)</a> connects to the simulated ROS 2 stack when a session is available.</p>
    <p><a href={`${BASE}v1/`} data-testid="v1-labs-link">The v1 archive</a> preserves the earlier labs and their links.</p>
    <h2>Credits and licences</h2>
    <p>COCO's CAD, robot and warehouse assets are Gautham Anil's work. COCO Lab is <a href={`${REPO_BLOB_URL}LICENSE`}>Apache-2.0 software</a>.</p>
    <p>Display type: Outfit. Interface type: Manrope. Both are self-hosted under the SIL Open Font License: <a href={`${BASE}licenses/outfit.txt`}>Outfit licence</a>, <a href={`${BASE}licenses/manrope.txt`}>Manrope licence</a>. Icons: Lucide, ISC, with the retained Feather MIT notice: <a href={`${BASE}licenses/lucide.txt`}>icon licence</a>.</p>
    <p><a href={`${REPO_BLOB_URL}docs/v2/ASSETS.md`}>Asset sources and checksums</a> · <a href={`${REPO_BLOB_URL}README.md`}>Project plan and contributors</a> · <a href={`${REPO_BLOB_URL}docs/RESULTS.md`}>Recorded results</a></p>
  </main>;
}
