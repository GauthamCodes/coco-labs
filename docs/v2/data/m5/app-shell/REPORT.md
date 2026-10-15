# M5.5 · App shell and routes

TESTED / MODEL. Start SHA 592d1d9, branch v2/m5-focus. Actual title, Play,
Compare and Research routes replace diagnostic references as the entry points.
The title draws the existing CAD robot first, then warms one self-hosted Python
worker without initializing a model session. Navigation claims that worker once;
explicit CDN clients remain independent. Warm-up failure permits a normal retry.
About explains evidence classes, the kinematic model, simulated Live Stack,
archive, credits and licences. Settings uses the canonical preferences module
for quality, walls, sound, bindings, theme and reduced motion; changes retain the
active model. Keyboard focus stays in the modal and returns to its opener.

Legacy Arena, Learn and Case File links retain their parameters and open their
new purpose; recording links open Research. Challenge/race and both M3/M4 share
formats remain Play. The frozen v1 archive is unchanged. Full robot inspection
remains reachable from Compare; Free roam remains reachable from Play.

## Verification

- Packages: 3534 passed, unchanged from M5.4; [log](packages.txt).
- Web: 466 passed versus 461 before; [log](vitest.txt). New route and worker
  ownership tests; typecheck passed [log](typecheck-final.txt).
- Build tools: 195 passed, unchanged; [log](tools.txt).
- Build and dist checks passed: [build](build-focus-and-title.txt), [dist](dist-final.txt).
- [URL checks](urls.txt): 50 forms plus six archive views, zero failures/console
  errors. Includes four real generated Arena run links, both hash versions and
  both shipped specs, reproducing exactly in their browser verifier.
- [Canvas](canvas.txt): five scenes, zero differing pixels. [Replays](replays.txt):
  five recordings, zero errors. No model/hash/golden change. CLI Play-link
  contract is unchanged; 137 committed links were verified at M5.3.
- [Warm/cold proof](verified/warm-model.json): both hash versions × both shipped
  specs, same initial world and all 25 state/chain hashes; warm-up emits no world.
  [Fault injection](warm-retry.json): corrupt warm ZIP rejected, next real boot
  retries successfully, zero console errors.
- [Shell checks](../screens/app-shell/revision3/shell-check.json): twenty real
  views plus four light Settings captures, four viewport profiles, zero console
  errors and third-party requests; focus containment and live preference updates.
  Earlier failed focus/selector runs are preserved, corrected final run passes.

## Conditions and limits

Node 24.21.0, Python 3.12.3 workspace venv. Browser artifacts contain conditions:
balanced, AC, reported NVIDIA 580.178.04; software GL captures are functional
checks, not GPU performance measurements. Phone layouts use the shared emulated
Nothing Phone (1) profile (CPU 4× proxy, touch/mobile, DPR 2.625). These tests
are not startup/FPS budget measurements. Real phone absent; [ADB](../phone/ADB_CHECK_M55.txt).
No pre-design observations or new owner feedback; blank notes retained.

Screenshots await Gautham's soft review. No files moved/removed, new ADR, parked
idea or stop condition. Play HUD and full phone interactions are M5.6; Compare
families/control sheet are M5.7; searchable Recordings is M5.8. No launch gate
or real Phone criterion is marked met. Next: M5.6 Play.
