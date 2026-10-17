# M5.6 Play review

Real app captures; Gautham's visual review is pending and nonblocking.
Earlier iterations, failures and interrupted runs remain in their directories.

Final layout captures:

- [closure-free](closure-free/): Free roam at 1440×900, 844×390, and emulated
  Nothing Phone (1) landscape 915×412 and portrait 412×915. Counts include the
  interactive world and joystick: 7 / 7 / 8 / 1 controls, no page scroll.
  Tutorial skipping is available in Settings or Escape; no counting exemption.
- [closure-games](closure-games/): six menus/games × those four profiles,
  24 captures. Includes the three decision games, mapping and race. All meet
  Focus; emulated phone control targets are at least 48 CSS px.
- [closure-scorecards](closure-scorecards/): four `*-scorecard-initial.png`
  captures show the initial scorecard; later captures retain the focus-test
  scroll position. All reproduce the actual shared hash and retain metrics.
  Portrait rotates to landscape for replaying the underlying game.
- [Interaction captures](../../play/closure-interactions/): real scan area and
  existing timeline instant replay. Hashes/input logs stay unchanged by vision
  and wall appearance; tutorial completion and reload are checked in its JSON.

Each JSON records conditions. Earlier captures were on AC; some resumed runs
were on battery; final closure captures record balanced/AC. These are layout
and functional checks, not performance budgets or real Adreno/phone results.
The real Nothing Phone (1) is not connected. Source/implementation report:
[Play report](../../play/REPORT.md).

The original five canvas baselines are preserved in [pre-play-hud](../pre-play-hud/).
Four remain identical; attract intentionally uses the full-screen canvas and
vision-off display. No golden MCAP or v1 state hash changed.
