# Submitting to the COCO-Bench leaderboard

The leaderboard ranks planners, controllers and localisers written against `coco_lab.api`
([API reference](../docs/v2/r2/API.md)) on the COCO-Bench v1 suites ([datasheets](../docs/bench/v1/README.md)). Every number on it was
computed by re-running the submitted file: nobody's word is taken for anything.

All results are **MODEL** evidence: COCO Lab's kinematic model, the same in the browser and
natively. Where an entry has also been run as a real ROS 2 node in Gazebo + Nav2, its page shows
those **STACK** results beside them, labelled.

## How to submit

1. Write your algorithm in the [Algorithm Studio](https://gauthamcodes.github.io/coco-labs/?view=workbench&tab=studio)
   or in any editor. It defines exactly one of `plan()`, `control()` or `localise()`.
2. Pick a board: a suite and the family your file implements.

   | Suite | Planners | Controllers | Localisers |
   | --- | --- | --- | --- |
   | `arena-nav-50` | yes | yes | yes |
   | `depot-nav-100` | yes | yes | yes |
   | `depot-narrow-30` | yes | yes | — |
   | `depot-long-50` | yes | yes | — |
   | `depot-clutter-50` | yes | yes | — |
   | `ctrl-corridor-30` | — | yes | — |
   | `ctrl-corners-30` | — | yes | — |
   | `ctrl-dynamic-30` | — | yes | — |
   | `loc-track-30` | — | — | yes |
   | `loc-global-20` | — | — | yes |
   | `loc-kidnap-20` | — | — | yes |

3. Make a directory `leaderboard/submissions/<suite>/<name>/` (`<name>`: lower-case letters,
   digits, `_` and `-`; 2–40 characters) holding exactly three files:
   - `algorithm.py` — your file, unchanged;
   - `meta.yaml`:

     ```yaml
     author: Your Name
     display_name: My planner
     description: One or two sentences on what it does.
     licence: MIT            # or Apache-2.0
     paper: https://...      # optional
     params:                 # optional: ctx.params for every run
       lookahead: 0.6
     ```
   - `summary.json` — your claim, written by the verifier's own command:

     ```bash
     python tools/r2/leaderboard.py claim leaderboard/submissions/<suite>/<name>
     ```

4. Open a pull request into `main` that changes **only** those three files.

## What happens to your pull request

1. **Leaderboard verify** (a `pull_request` workflow: no secrets, read-only) builds the verifier
   from the *base branch* and runs your file in a container with no network, a read-only file
   system, no capabilities, 2 CPUs, 4 GB and a time limit. It:
   - runs your file on every public scenario of the suite **and** on held-out scenarios (below);
   - runs **every run twice**: the two hash chains must be identical (a non-deterministic
     algorithm can be run in the Studio, labelled, but cannot be submitted);
   - checks the contract (paths, Twists, covariances; see the API reference) and counts clamped
     outputs;
   - compares your `summary.json` digest with the one it computed.
2. **Leaderboard results** (a separate, trusted workflow that never runs your code) reads the
   verifier's artifact as data, comments the report on your PR and labels it `verified` or
   `not-verified`. For a pull request from a branch of this repository it also commits the
   verified result (`leaderboard/results/<suite>/<name>/result.json`); for a fork, the result is
   in the comment and a maintainer adds it when merging.
3. A maintainer reviews the code and merges. Merged entries are re-verified automatically
   whenever the model, the API, a suite or the verifier changes.

## How entries are ranked

Deterministic metrics only, in this order (ties go to the next):

| Family | 1st | 2nd | 3rd | 4th |
| --- | --- | --- | --- | --- |
| Planners | success rate (Wilson 95% shown) | median path length ÷ grid-optimal length | median minimum clearance (higher first) | median expansions (self-reported) |
| Controllers | success rate | median time to goal | median minimum clearance | — |
| Localisers | success rate | median final position error | — | — |

*Grid-optimal* is Dijkstra's 8-connected path with no cost term on the same costmap: an any-angle
planner can beat it (a ratio below 1). *Expansions* are counted from your `ctx.emit('expand', ...)`
events, so they are only as honest as your file: they are shown, labelled self-reported, and rank
last. **Compute time is shown per device and never ranks anything.**

## Rules

- **No hard-coding scenarios.** Your file must not contain scenario coordinates, seeds, suite
  data or anything that recognises a particular scenario. Reviewers reject it.
- **Held-out scenarios.** Each suite has held-out variants: scenarios drawn by the suite's own
  generator with the seed `sha256("coco-lab.leaderboard.held-out.v1|<suite>|<merge-base sha>")`.
  The leaderboard shows public and held-out results side by side; a large gap is a sign of
  overfitting. **Stated limitation:** this scheme has no secret. The salt is in the repository,
  so anyone who knows a pull request's merge-base can compute its held-out set before opening it.
  It catches overfitting by habit or chance, not a determined cheat — that is what review and the
  hard-coding rule are for. (ADR 0012; a secret-free scheme cannot do better.)
- **Licence:** MIT or Apache-2.0, stated in `meta.yaml`. By submitting you confirm you may
  license the file so.
- **The sandbox's limits** (ADR 0012) apply: allowed imports only (`math`, `heapq`,
  `collections`, `itertools`, `functools`, `bisect`, `typing`, `dataclasses`, `random` through the
  run's seeded generator, `coco_lab.api`), no attribute names starting with `_`, a step budget
  per call. A file that loads in the Studio loads in the verifier.
- **One entry per algorithm per board**; improve it by updating your directory in a new PR.

## Code of conduct

Be kind, assume good faith, and keep discussion about the work. Harassment, personal attacks and
discriminatory language are not tolerated; maintainers may close pull requests or hide comments
that break this. Report problems to the repository owner. Gaming the benchmark — hard-coded
scenarios, hiding work from `ctx.emit`, probing the sandbox — gets an entry removed.
