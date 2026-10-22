// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.13: which GPU the G1 measurement tools launch Chromium on, from G1_GPU.
 *
 *   G1_GPU=software (default; the cloud and CI): SwiftShader, as before.
 *   G1_GPU=nvidia: ANGLE on EGL, the default EGL vendor (the laptop's RTX 4050), M4.1's recipe.
 *   G1_GPU=intel: ANGLE on Vulkan with Mesa's Intel driver (VK_ICD_FILENAMES), M4.1's recipe:
 *     forcing EGL onto Mesa made Chromium fall back to SwiftShader.
 *
 * The page's own WebGL renderer string is recorded by each tool (`renderer(page)`), and
 * `assertGpu` refuses a run whose renderer is not the GPU asked for, so a number is never
 * attributed to the wrong GPU.
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

export const GPU = process.env.G1_GPU || 'software';
const INTEL_ICD = '/usr/share/vulkan/icd.d/intel_icd.json';

export function launchOptions() {
  const args = GPU === 'nvidia' ? ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu']
    : GPU === 'intel' ? ['--use-angle=vulkan', '--enable-features=Vulkan', '--ignore-gpu-blocklist', '--enable-gpu']
      : ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'];
  const env = { ...process.env };
  if (GPU === 'intel') env.VK_ICD_FILENAMES = INTEL_ICD;
  return { ...(process.env.G1_CHROMIUM ? { executablePath: process.env.G1_CHROMIUM } : {}), args, env };
}

/** The renderer string of a fresh WebGL2 context in the page (the same GPU process). */
export async function renderer(page) {
  return page.evaluate(() => {
    const gl = document.createElement('canvas').getContext('webgl2');
    if (!gl) return 'no webgl2';
    const e = gl.getExtension('WEBGL_debug_renderer_info');
    return String(gl.getParameter(e ? e.UNMASKED_RENDERER_WEBGL : gl.RENDERER));
  });
}

export function assertGpu(r) {
  const want = GPU === 'nvidia' ? /NVIDIA/i : GPU === 'intel' ? /Intel/i : /SwiftShader/i;
  if (!want.test(r)) throw new Error(`G1_GPU=${GPU} asked, but the page renders on: ${r}`);
}

/** The machine's state for a measurement (AC, power profile, drivers). */
export function machine() {
  const sh = (cmd, args) => { try { return execFileSync(cmd, args, { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim(); } catch { return 'unavailable'; } };
  let ac = 'unknown';
  try { ac = readFileSync('/sys/class/power_supply/AC0/online', 'utf8').trim() === '1' ? 'on AC' : 'on battery'; } catch {
    try { ac = readFileSync('/sys/class/power_supply/ACAD/online', 'utf8').trim() === '1' ? 'on AC' : 'on battery'; } catch { /* unknown */ }
  }
  return {
    gpu_asked: GPU,
    power_profile: sh('powerprofilesctl', ['get']),
    ac,
    nvidia: sh('nvidia-smi', ['--query-gpu=name,driver_version,pstate,temperature.gpu', '--format=csv,noheader']),
    mesa: sh('dpkg-query', ['-W', '-f', '${Version}', 'libgl1-mesa-dri']),
    kernel: sh('uname', ['-r']),
    cpu: (sh('lscpu', []).match(/Model name:\s+(.*)/) || [null, 'unavailable'])[1],
  };
}
