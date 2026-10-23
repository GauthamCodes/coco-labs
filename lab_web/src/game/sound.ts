// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1: the game's sounds, synthesised with WebAudio (our own synthesis; no
 * files). Muted until the person's first interaction (browsers require it)
 * and whenever the Sound setting is off. The motor hum's pitch and level
 * follow the model's real speed; nothing here pretends a quantity the model
 * does not have.
 */

type Ctx = AudioContext;

export class GameSound {
  private ctx: Ctx | null = null;
  private master: GainNode | null = null;
  private hum: { osc: OscillatorNode; osc2: OscillatorNode; gain: GainNode; filter: BiquadFilterNode } | null = null;
  enabled: boolean;

  constructor(enabled: boolean) { this.enabled = enabled; }

  /** Call from a user gesture: creates (or resumes) the context. */
  unlock() {
    if (!this.enabled) return;
    try {
      if (!this.ctx) {
        const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
        if (!AC) return;
        this.ctx = new AC();
        this.master = this.ctx.createGain();
        this.master.gain.value = 0.5;
        this.master.connect(this.ctx.destination);
      }
      void this.ctx.resume();
    } catch { this.ctx = null; }
  }

  setEnabled(on: boolean) {
    this.enabled = on;
    if (this.master) this.master.gain.value = on ? 0.5 : 0;
    if (!on) this.motor(0, 1);
  }

  /** The motor hum: `speed` (m/s, the model's) over `max` (the robot's real limit). */
  motor(speed: number, max: number) {
    const c = this.ctx;
    if (!c || !this.master) return;
    if (!this.hum) {
      const osc = c.createOscillator(), osc2 = c.createOscillator(), gain = c.createGain(), filter = c.createBiquadFilter();
      osc.type = 'sawtooth'; osc2.type = 'square'; filter.type = 'lowpass'; filter.frequency.value = 600;
      gain.gain.value = 0;
      osc.connect(filter); osc2.connect(filter); filter.connect(gain); gain.connect(this.master);
      osc.start(); osc2.start();
      this.hum = { osc, osc2, gain, filter };
    }
    const f = Math.min(1, Math.abs(speed) / Math.max(1e-6, max));
    const t = c.currentTime;
    this.hum.osc.frequency.setTargetAtTime(55 + 140 * f, t, 0.08);
    this.hum.osc2.frequency.setTargetAtTime(110 + 280 * f, t, 0.08);
    this.hum.filter.frequency.setTargetAtTime(380 + 900 * f, t, 0.1);
    this.hum.gain.gain.setTargetAtTime(this.enabled && f > 0.01 ? 0.03 + 0.07 * f : 0, t, 0.06);
  }

  private tone(freq: number, dur: number, type: OscillatorType, vol: number, at = 0, slide?: number) {
    const c = this.ctx;
    if (!c || !this.master || !this.enabled) return;
    const t = c.currentTime + at;
    const o = c.createOscillator(), g = c.createGain();
    o.type = type; o.frequency.setValueAtTime(freq, t);
    if (slide) o.frequency.exponentialRampToValueAtTime(slide, t + dur);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(this.master);
    o.start(t); o.stop(t + dur + 0.02);
  }

  private noise(dur: number, vol: number, cutoff: number) {
    const c = this.ctx;
    if (!c || !this.master || !this.enabled) return;
    const n = Math.floor(c.sampleRate * dur), buf = c.createBuffer(1, n, c.sampleRate), d = buf.getChannelData(0);
    let s = 12345;
    for (let k = 0; k < n; k++) { s = (s * 1103515245 + 12345) & 0x7fffffff; d[k] = ((s / 0x7fffffff) * 2 - 1) * (1 - k / n) ** 2; }
    const src = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain();
    src.buffer = buf; f.type = 'lowpass'; f.frequency.value = cutoff; g.gain.value = vol;
    src.connect(f); f.connect(g); g.connect(this.master); src.start();
  }

  grab() { this.tone(180, 0.12, 'square', 0.18, 0, 90); this.noise(0.08, 0.25, 900); }
  deliver() { [523, 659, 784, 1047].forEach((f, k) => this.tone(f, 0.18, 'triangle', 0.16, k * 0.08)); }
  stop() { this.tone(110, 0.35, 'sawtooth', 0.22); this.tone(116, 0.35, 'sawtooth', 0.18); }
  contact() { this.noise(0.18, 0.5, 260); this.tone(70, 0.18, 'sine', 0.3, 0, 40); }
  click() { this.tone(880, 0.04, 'square', 0.06); }
  refuse() { this.tone(300, 0.12, 'square', 0.1); this.tone(220, 0.14, 'square', 0.1, 0.1); }

  dispose() { try { void this.ctx?.close(); } catch { /* closed already */ } this.ctx = null; this.hum = null; }
}

/** Haptics: a short tick, a double tick, a long buzz; silent when the device or the setting says no. */
export function haptic(kind: 'grab' | 'deliver' | 'stop' | 'contact' | 'tick', enabled: boolean) {
  if (!enabled) return;
  const pattern = { grab: [18], deliver: [20, 60, 20], stop: [120], contact: [40, 30, 40], tick: [8] }[kind];
  try { navigator.vibrate?.(pattern); } catch { /* unsupported */ }
}
