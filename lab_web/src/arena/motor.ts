// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The optional motor sound (M4.5; README §5.5): off by default, pitched to the
 * wheel speed the model reports (Tick.wheels), never to anything invented.
 * Presentation only. The AudioContext is made on the person's own click (a
 * browser plays nothing before one), and closed when the sound is turned off.
 */

/** Pitch at rest and per rad/s of mean wheel speed (Hz); loudness while turning, at most (0..1). */
const BASE_HZ = 55;
const HZ_PER_RAD_S = 9;
const MAX_GAIN = 0.05;

export class MotorSound {
  private ctx: AudioContext | null = null;
  private osc: OscillatorNode | null = null;
  private gain: GainNode | null = null;

  get on(): boolean {
    return this.ctx !== null;
  }

  /** Start (inside a click handler). Returns false where the browser has no Web Audio. */
  start(): boolean {
    if (this.ctx) return true;
    try {
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.value = BASE_HZ;
      gain.gain.value = 0;
      const lp = ctx.createBiquadFilter();
      lp.type = 'lowpass';
      lp.frequency.value = 600;
      osc.connect(lp).connect(gain).connect(ctx.destination);
      osc.start();
      Object.assign(this, { ctx, osc, gain });
      return true;
    } catch {
      return false;
    }
  }

  stop() {
    try { this.osc?.stop(); void this.ctx?.close(); } catch { /* already closed */ }
    this.ctx = null; this.osc = null; this.gain = null;
  }

  /**
   * Follow the wheels (rad/s, left and right): pitch from their mean speed, loudness from how hard they
   * turn relative to `full` (rad/s: the teleop maximum over the spec's wheel radius).
   */
  update(wheels: [number, number], full: number) {
    if (!this.ctx || !this.osc || !this.gain) return;
    const speed = (Math.abs(wheels[0]) + Math.abs(wheels[1])) / 2;
    const t = this.ctx.currentTime;
    this.osc.frequency.setTargetAtTime(BASE_HZ + HZ_PER_RAD_S * speed, t, 0.05);
    this.gain.gain.setTargetAtTime(MAX_GAIN * Math.min(1, speed / Math.max(full, 1e-6)), t, 0.05);
  }
}
