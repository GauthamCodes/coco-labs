# Hotfix: never a blank page without WebGL (evidence)

Gautham, 2026-10-24: the deployed site showed an empty dark page in Brave, intermittently. Cause:
when the browser refused a WebGL context, three.js threw `Error creating WebGL context` inside a 3D
view, and with no error boundary React unmounted the whole app.

## What the page does now (WebGL refused)

| Page | Shows |
|---|---|
| Title | the menus (every door is a link) on a plain background, why the Depot is not drawn, what to try |
| Play | a message page: what happened, **what to try** (reload, hardware acceleration, other 3D tabs, chrome://gpu), **works without 3D: Compare, Recordings**, Reload, the title |
| Compare | the comparison runs and lists its results; the map is replaced by a note with what to try |
| Research (Recordings), About | unchanged (no WebGL used) |

Any other page error shows "Something went wrong", Reload and links to the title, Compare and Recordings.
With WebGL working nothing changes.

## Check

`lab_web/tools/webgl_fallback_check.mjs SITE OUT.json SHOT_DIR`: Chromium (Playwright) launched with
`--disable-webgl --disable-3d-apis`, then with WebGL (SwiftShader). A page fails if it is blank, logs a
page error, lacks its expected fallback, Play's page lacks the Compare and Recordings links, or Compare
does not finish its comparison (`data-ready`). Result on this build (2026-10-25, laptop, served `dist`):
[`webgl_fallback_check.json`](webgl_fallback_check.json), 10 of 10 pages pass; screenshots with WebGL
refused in [`screens/`](screens/). vitest 539/539, typecheck, `check_dist` pass.

UI only: no model, protocol or hash change.
