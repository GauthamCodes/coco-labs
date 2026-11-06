# R3 prompt — land R2, then R3 · COCO-Bench v1 and the paper (with merge and deploy authority)

Issued by Gautham 2026-11-06. Saved verbatim in substance (formatting kept) by the agent at the start of
Part A. Progress: Part A in [`LANDING_STATUS.md`](LANDING_STATUS.md), Part B in [`R3_STATUS.md`](R3_STATUS.md).

Resume: "Continue COCO Lab: read `docs/v2/r3/R3_PROMPT.md` and `docs/v2/r3/R3_STATUS.md` (or
`docs/v2/r3/LANDING_STATUS.md` if Part A isn't finished), then carry on from the next step."

---

You are continuing COCO Lab (repo `GauthamCodes/coco-labs`, live at https://gauthamcodes.github.io/coco-labs/).
R2 · Bring Your Own Algorithm is finished as PR #32 (unmerged). Gautham's Lazy Theta* submission is PR #31.

This session has two parts:
- **Part A:** land R2, now that you are allowed to merge and deploy.
- **Part B:** build **R3 · COCO-Bench v1 and the paper**, which turns COCO Lab into a citable research benchmark.

## 0. New standing authority (Gautham, 2026-11-06): record it in `docs/STATUS.md` and README §9

**From now on, Claude Code may open, update, merge and deploy its own pull requests, and do the git and GitHub
housekeeping, without asking first,** on these conditions:

1. **Merge gate.** All of the following must be true before merging:
    - every required CI check is green on the PR's **exact head**
    - local suites pass
    - no stop condition has fired
    - a short self-review is written to the PR (what changed, the risks, the evidence)

    **The single exception:** when `build-and-test` fails **only** inside "Setup ROS 2 Jazzy" (before any
    repository code runs), you may merge if you re-ran it up to 3 times, the same workflow passed on a commit
    with the **identical source tree** for everything except docs, and the PR comment links both runs. Fixing
    that step in CI (caching, a pinned mirror, or a timeout plus retry) is part of Part A.
2. **How to merge:** merge commits, never squash, so the `[R…]` checkpoint history stays; never force-push and
   never rewrite pushed history; you may retarget a PR's base branch, rebase **unpushed** work, and merge `main`
   into feature branches; after merging, keep the feature branch (don't delete it).
3. **How to deploy:** `gh workflow run lab.yml --ref main -f confirmation=DEPLOY`, then wait for it to finish;
   then a **live smoke test** with Playwright against the public URL: title, Play (a Fetch Rush round starts and
   moves), Compare, Workbench (a small experiment runs), Studio (the A* starter runs), Leaderboard, Learn; also
   check the "New version ready" path for an already-open tab; record the deploy run ID and the smoke-test
   results in STATUS.
4. **If the live site breaks:** open a revert PR immediately (`git revert -m 1 <merge>`), merge it under the
   same gate (a revert may skip waiting for the full Gazebo checks, but not the web and unit checks), redeploy,
   and report. Never force-push `main`.
5. **Still Gautham's call**, so ask, or prepare and stop: GitHub releases and tags; deleting branches; anything
   in the COCO robot repository; publishing outside GitHub: arXiv, Zenodo DOIs, LinkedIn, emails, workshop
   submissions; changing licences; spending money.
6. **Every earlier rule still holds:** rendering never changes the model; hashes are versioned; evidence labels
   are truthful; statistics are honest; never invent numbers; never delete evidence. Security: the R2 sandbox and
   the CI security model. Machine: balanced profile on AC; one simulator at a time; never Gazebo `--fast`. The
   phone: restore its settings afterwards; black out its status bar in screenshots. The laptop: if it suspends,
   resume where it stopped and say so.

## Part A · Land R2 (progress in `docs/v2/r3/LANDING_STATUS.md`, committed on `v2/r2-byoa`)

### A1. Gautham's answers to the R2 questions (record them in R2_RESULTS and STATUS, dated 2026-11-06)

1. **D* Lite's 3e-15:** exactness is the project's promise, so make the adapter add up the path in the same order
   as the native code, so results are byte-identical. If that can't be done without changing goldens, document a
   1e-12 tolerance for **derived float metrics only** (never for counts or hashes), as an ADR note.
2. **Lazy Theta*'s 0/5 drives:** keep it as a **visible negative row**; hiding failures is never allowed. Record
   the costmap cost along each Theta* path in a re-run of the 5 drives to confirm or reject the "hugs corners"
   explanation, and state the result.
3. **Snapping Nav2's start and goal to free cells:** report **both**, stock Nav2 (unchanged) and "snapped" (start
   and goal moved to the nearest free cell, as COCO Lab does), clearly labelled.
4. **Studio view first on a phone in landscape:** yes.
5. **The other questions in R2_RESULTS.md:** decide them yourself using these principles, and record each decision
   and its reason: exact reproducibility first; no hidden failures; honest labels; the smallest change that serves
   learners and researchers. Ask only if a decision is irreversible.

### A2. Fixes before merging

1. The double-build check, failing on `main` since R1: dataset/Colab links and the sandbox probe URL. Fix the
   check or the build so it's deterministic, and make sure it can't be hidden locally again.
2. The Studio light theme's 92 contrast failures: fix them, to WCAG AA.
3. The lint errors in the ROS 2 exporter and the starters.
4. Harden the ROS 2 CI setup so runner timeouts stop recurring (cache, pinned mirror, or a timeout with retry).
5. The test that expects the Theta* submission: make it skip cleanly unless the submission exists.

### A3. Merge, retarget, deploy

1. Merge PR #32 under the gate.
2. Retarget PR #31 to `main`, merge `main` into it, and confirm the verifier labels it **verified** (public and
   held-out). Then merge it under the gate. Gautham's Theta* becomes the first community-style entry.
3. Deploy and run the live smoke test (§0.3).
4. The real phone: if `adb devices` lists it, run the Studio and Workbench phone checks on the live site.

## Part B · R3 · COCO-Bench v1 and the paper (branch `v2/r3-bench-paper` from the new `main`)

**Why:** R1 and R2 made COCO Lab a working lab. R3 makes it **a benchmark people can cite**: versioned suites with
datasheets; browser-model results **paired with real Gazebo + Nav2 results** on the same scenarios; a paper whose
every number regenerates from committed data, with one link that re-runs the paper's experiments in anyone's
browser. This is the strongest artefact for Gautham's TUM RCI application and his robotics job search.

Save this part as `docs/v2/r3/R3_PROMPT.md`, track progress in `R3_STATUS.md`, commit `[R3.n]` and push. Add R3 to
README §7 and STATUS.

### B1. COCO-Bench v1 suites (frozen and versioned; each with a datasheet)

- **Global planning:** `arena-nav-50` and `depot-nav-100` (carried over from v0 with identical scenarios; bump to
  v1 only if metadata changes); `depot-narrow-30`; `depot-long-50` (long-horizon routes across several zones);
  `depot-clutter-50` (extra static obstacles generated from the kit, so a scenario looks only as cluttered as it
  really is).
- **Local control:** `ctrl-corridor-30`, `ctrl-corners-30`, `ctrl-dynamic-30` (moving actors under Rules 5, both
  yielding and non-yielding variants, clearly labelled as scenario rules).
- **Localisation:** `loc-track-30` (tracking from a known start), `loc-global-20` (global localisation from an
  unknown start), `loc-kidnap-20` (kidnapped robot). Use the existing Lab 2 kidnap methodology where it applies.
- **Full task:** `task-fetch-12` (Fetch Rush phone rounds plus the colour rounds).

For each suite:
- **Difficulty tiers:** easy, medium, hard, defined by measurable features (path length, narrowest clearance,
  turns, actor density). Report results per tier.
- **Held-out sets:** improve on R2's scheme. The **trusted** workflow generates the held-out scenarios with a
  **secret salt**, *outside* the sandbox, and passes only the scenario file into the no-network, unprivileged
  container; the secret never enters the container's environment or filesystem. Have the design security-reviewed
  first: write it in ADR 0014 together with its threat analysis, and test it with hostile submissions that try to
  exfiltrate or memorise the held-out scenarios. If it can't be done safely, keep R2's scheme and its stated
  limitation.
- **A datasheet** (`DATASHEET.md`): purpose, generation procedure and seeds, metric definitions with formulas,
  tiers, known biases and limitations (the kinematic model, a single robot, no hardware), versioning, and the
  licence.

### B2. Baselines and the model-vs-ROS 2 gap

1. **Browser model baselines:** every built-in algorithm on every v1 suite, public and held-out, committed with
   manifests.
2. **Real Gazebo + Nav2 baselines** on a **validated subset** of each navigation and control suite, at least 20
   scenarios per suite and 3 repeats each. Planners: NavFn, Smac 2D, Smac Hybrid-A*, and the user-node A* from R2.
   Controllers: DWB, RPP, MPPI. Localisation: AMCL against the R2 particle-filter starter. Run them stock **and**
   snapped (A1.3). Long laptop runs: resumable checkpoints, one simulator at a time, raw logs in
   `~/coco_lab_runs/r3/`.
3. **The gap analysis:** the browser model against real Nav2 on the same scenarios, per metric: agreement in
   success and failure (with a confusion table); path-length ratios; where the model is optimistic or pessimistic,
   and why (the kinematic model, AMCL drift, controller differences). Publish it as a **"Model vs ROS 2" page** in
   Workbench, with all paired runs downloadable.

### B3. Leaderboard v1

1. Boards for every v1 suite, including controllers and localisers.
2. Re-verify all entries under v1, including the Theta* submission and the built-ins.
3. Each entry gets public and held-out results, tiers, failures, and the "Browser vs ROS 2" panel where real runs
   exist.
4. Add a "Submit" guide page in the site linking CONTRIBUTING.

### B4. The paper (`docs/paper/`)

1. A workshop-length paper in LaTeX (6–8 pages, plus a reproducibility appendix), author **Gautham** (confirm his
   preferred name form and affiliation in the report; use "Gautham, Amrita Vishwa Vidyapeetham" until confirmed).
   Working title: *"COCO-Bench: Reproducible, Browser-Based Benchmarking of Mobile-Robot Navigation, Validated
   Against ROS 2 and Gazebo."*
2. Sections: Introduction (the reproducibility problem in robot navigation benchmarking); Related work (real
   citations only, each one checked; anything unverified is marked [CHECK]); System (the Python model in Pyodide;
   determinism across 4 engines with hashed traces; the ROS 2-shaped API; the sandboxed verified leaderboard;
   export of user code to real ROS 2 nodes); Benchmark design (suites, tiers, held-out scenarios, metrics);
   Experiments (baselines; the model-vs-ROS 2 gap; the bring-your-own-algorithm case study: Theta*, including its
   honest Gazebo failure); Limitations (kinematic model, single robot, no hardware; the Live Stack is simulated;
   phone results are emulated where they are emulated); Conclusion.
3. Every figure and table is generated by scripts in `docs/paper/scripts/` from committed data, with `make`
   reproducing the whole PDF. No number is typed by hand: numbers come in through generated `\newcommand` macros,
   and CI fails if the PDF's numbers drift from the data.
4. "Reproduce this paper": one link that opens the Workbench with the paper's browser experiments pre-loaded and
   verifies they match.
5. Add `CITATION.cff` to the repository root, and a "Cite" button on the site.
6. Prepare but don't submit an arXiv-ready source bundle and a list of suitable workshop venues with deadlines
   (verify each deadline on the web and cite it). Submitting is Gautham's call.

### B5. Launch kit (drafts in `docs/launch/`; publishing is Gautham's call)

A 90-second demo video shot list and script (Play → SIM → Workbench → Studio → Run in ROS 2 → leaderboard); a
LinkedIn post plus a shorter version; résumé bullets, with numbers taken only from evidence; a one-page
architecture diagram (SVG); an updated repository README front page: what it is, live link, GIF placeholders,
quick start, cite.

### B6. Close

1. Verify: all suites; v1/v2/v3 determinism on 4 engines; parity; security tests; the paper builds from a clean
   checkout; Play fps unchanged; the real phone if connected.
2. Write up: `R3_RESULTS.md` and `BEFORE_AFTER.md`.
3. Ship: open the PR "R3 · COCO-Bench v1 and the paper", self-review it, merge it under the gate, deploy, run the
   live smoke test, and record everything in STATUS.

## Stop and report if

- Any golden or model hash changes unexpectedly.
- A sandbox or held-out exfiltration test succeeds.
- The paper would need a number with no committed source.
- Real Gazebo + Nav2 can't run without changing COCO's robot repository.
- The live site fails its smoke test and a revert doesn't fix it.

## Final report

```
Part A: decisions applied; fixes; PR #32 merged (SHA, CI run IDs); PR #31 verified and merged; deploy run ID; live smoke-test results; phone
Part B checkpoints done:
Suites: list with scenario counts, tiers, held-out scheme (ADR 0014 result)
Baselines: browser (all suites) | Gazebo + Nav2 (subset sizes, stock vs snapped)
Gap analysis: headline findings with numbers and evidence paths
Leaderboard v1: boards, entries, re-verification results
Paper: PDF path, page count, "reproduce" link result, venues list (with sources)
Launch kit: files
Tests, determinism, security, Play fps:
PR(s) merged and deploys (IDs), live smoke results:
Questions for Gautham (including name/affiliation for the paper, and any submission decisions):
Next step (R4 · Learn course):
```
