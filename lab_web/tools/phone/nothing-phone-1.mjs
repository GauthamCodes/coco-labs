// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Assumed viewport profile. This emulates viewport/CPU/network, not an Adreno GPU. */
export const DEVICE_NAME = 'emulated Nothing Phone (1)';
export function nothingPhone1(landscape = false) {
  return {
    viewport: landscape ? { width:915, height:412 } : { width:412, height:915 },
    deviceScaleFactor:2.625, isMobile:true, hasTouch:true,
    userAgent:'Mozilla/5.0 (Linux; Android 12; Nothing Phone (1)) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Mobile Safari/537.36',
  };
}
export async function throttlePhone(context, page, cold = false) {
  const cdp = await context.newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate:4 });
  if (cold) { await cdp.send('Network.enable'); await cdp.send('Network.emulateNetworkConditions', {offline:false, latency:170, downloadThroughput:9e6/8, uploadThroughput:1.5e6/8}); }
  return cdp;
}
