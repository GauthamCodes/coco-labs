/**
 * The machine's measurement conditions, recorded next to every harness's
 * results (owner's rule, 2026-10-09, docs/STATUS.md plan-change log): the
 * power profile, AC or battery, the CPU governor and the load average. The
 * standard is the BALANCED profile on AC power; a result taken otherwise is
 * kept and labelled, never silently compared with one taken on the standard.
 *
 * M1.10 measured in power-saver without noticing until the cold-start
 * harness recorded it; M1.5 recorded nothing, so the two could not be
 * compared. Reading these costs ~1 ms and never throws.
 */
import { execFileSync } from 'node:child_process';
import { readdirSync, readFileSync } from 'node:fs';
import os from 'node:os';

const read = (path) => { try { return readFileSync(path, 'utf-8').trim(); } catch { return null; } };

export function conditions() {
  let profile = 'unknown';
  try { profile = execFileSync('powerprofilesctl', ['get'], { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim(); } catch { /* not available */ }
  let ac = null;
  let battery = null;
  try {
    for (const name of readdirSync('/sys/class/power_supply')) {
      const dir = `/sys/class/power_supply/${name}`;
      const type = read(`${dir}/type`);
      if (type === 'Mains') ac = (ac ?? false) || read(`${dir}/online`) === '1';
      if (type === 'Battery') battery = { status: read(`${dir}/status`), capacity_pct: Number(read(`${dir}/capacity`)) };
    }
  } catch { /* no power-supply class (not a laptop, or not Linux) */ }
  const governors = new Set();
  for (let i = 0; i < os.cpus().length; i += 1) {
    const g = read(`/sys/devices/system/cpu/cpu${i}/cpufreq/scaling_governor`);
    if (g) governors.add(g);
  }
  const load = os.loadavg().map((x) => Math.round(x * 100) / 100);
  return {
    at_utc: new Date().toISOString(),
    power_profile: profile,
    ac_power: ac,
    battery,
    cpu_governor: governors.size ? [...governors].sort().join(',') : 'unknown',
    load_average: { '1m': load[0], '5m': load[1], '15m': load[2] },
    cpu: os.cpus()[0]?.model ?? 'unknown',
    threads: os.cpus().length,
    // The standard conditions for COCO Lab timings: balanced profile, on AC.
    standard: profile === 'balanced' && ac === true,
  };
}
