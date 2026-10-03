// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The ONE place the site's deployment constants live.
 *
 * `DEFAULT_BASE` is the GitHub Pages project path (the repository's name).
 * `vite.config.ts` uses it unless the environment variable `LAB_BASE`
 * overrides it (e.g. `LAB_BASE=/ npm run build` for a root-served copy).
 * Application code never writes a path prefix: it uses Vite's
 * `import.meta.env.BASE_URL`, which is this value at build time.
 *
 * The Pyodide pin is here too, because both `index.html`'s CSP and the
 * worker must name exactly the same CDN directory (a test asserts it).
 */
export const DEFAULT_BASE = '/coco-labs/';

/**
 * Where the Live tab may open a coco.v1 WebSocket (the CSP's connect-src).
 * The local stack, plus the one remote endpoint below when it is set --
 * never by widening this to every `ws:`/`wss:`.
 */
export const LIVE_CONNECT_SRC_LOCAL: readonly string[] = ['ws://localhost:*', 'ws://127.0.0.1:*'];

/**
 * The scheduled REMOTE session's endpoint (Phase 2 Part C): the coco.v1
 * WebSocket. The public Live tab probes the same host's /healthz to say
 * "live now" truthfully -- only when that endpoint reports an open session,
 * never because it is set here. The owner's Tailscale Funnel
 * (docs/live/tunnel/README.md); offline between sessions. Setting it adds
 * exactly this host's wss: and https: origins to the CSP, nothing wider.
 */
export const LIVE_REMOTE: { ws: string } | null = { ws: 'wss://coco-live.taile7cb60.ts.net/ws' };

/** The remote endpoint's two origins, for the CSP; none when unset. */
export function remoteConnectSrc(remote: { ws: string } | null): string[] {
  if (!remote) return [];
  const u = new URL(remote.ws);
  if (u.protocol !== 'wss:') throw new Error(`LIVE_REMOTE must be wss://, got ${remote.ws}`);
  return [`wss://${u.host}`, `https://${u.host}`];
}

/**
 * The CSP's WebSocket/probe origins: local, plus the remote endpoint's two.
 * A function, called only by vite.config.ts at build time, so none of it is
 * shipped in the page bundle.
 */
export function liveConnectSrc(): string[] {
  return [...LIVE_CONNECT_SRC_LOCAL, ...remoteConnectSrc(LIVE_REMOTE)];
}

/** Run the whole stack yourself: the Docker quickstart. */
export const DOCKER_QUICKSTART_URL = 'https://github.com/GauthamCodes/coco-labs/blob/main/docs/DOCKER.md';

/** Looked up 2026-09-30 (GitHub releases + npm); Python 3.14.2 inside. */
export const PYODIDE_VERSION = '314.0.7';
export const PYODIDE_INDEX_URL =
  `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
