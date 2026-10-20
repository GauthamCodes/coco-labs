# M5 closure attempt — 2026-10-20

M5 remains open. The owner explicitly requested a report and stop if the native
control discrepancy was not a trajectory-scoring tie. The diagnosis below finds
LiDAR-to-costmap cell rasterization differences, not a scoring tie. No guessed
algorithm fix, hash-version bump or golden edit was made. The remaining closure
implementation and final-head measurement sequence has therefore not run.

## Native/Pyodide diagnosis (MODEL, differential test)

Measured model source at `51c2216b21a86027a540c746d183056d1cb68fc8`;
the controller/model source is unchanged from the reviewed head. CPython 3.12
and Pyodide Python 3.14, existing pinned toolchain. The trace uses the review's
control request, existing world, goal, seed and inflation; two MPPI arms repeat
the same computation independently. This is a correctness diagnostic, not a
performance measurement. Original four-pane review captures remain intact.

[Machine-readable diagnosis](native-diagnosis.json) and complete losslessly
compressed [native](native-trace.json.gz) /[Pyodide](pyodide-trace.json.gz) traces
retain inputs, per-sample scores, poses, local paths, costmaps, ray indices and
output frames. Uncompressed SHA256 values are in the diagnosis. Reproduce with
`node docs/v2/data/m5/closure-20261020/trace_mppi.mjs OUTDIR` after building Arena
assets; create OUTDIR first. The runner uses the pinned local Python venv.

- Hashes first differ at tick 0 (already in the review); the cause of the hash
  serialization difference itself is not asserted here.
- First numeric MPPI frame difference: tick 1, pose X differs by
  `6.071532165918825e-18` m.
- First local costmap difference in the original four-arm request: tick 3,
  DWA arm A, 30 cells differ. Ray 116 maps to cell 109 in CPython and 108 in
  Pyodide, with ranges `1.8479669224086284` and `1.8479669224086273`. These
  near-boundary LiDAR endpoints pass through `LocalWindow.index`'s `floor`.
- First sample-score discrepancy over `1e-9`: tick 45, sample 49. Its obstacle
  critic is `0.00562429696287964` in native and `0` in Pyodide; the native
  trajectory encounters a cost-20 cell while the Pyodide trajectory sees zero.
  Other score components are effectively equal at this point. This changes
  MPPI's exponential weights and warm-start sequence.
- MPPI does not choose the minimum-score sample: it produces a weighted control
  sequence from all samples. Rounding comparator scores and breaking ties by
  index does not address this rasterization discontinuity.

DWA first chooses different candidates at tick 47: native selects index 32,
Pyodide index 12. Candidate 32 has the same velocity and effectively identical
trajectory in both runtimes, but its obstacle critic is 0 versus 22, changing
its weighted total from `1679.4638041608869` to `1855.4638041608869`.
Candidate 12 costs `1700.3884872002966` in both. The native best/runner-up gap
is about 3.113; Pyodide's is about 2.182. **Neither decision is a near-tie.**
The first grid discontinuity above predates the decision change.

The review's exact maximum `0.446011142799704` m is reproduced at tick 48,
DWA arm A, chosen trajectory Y element 4: native `1.041119646173946`,
Pyodide `1.48713078897365`. [Four-arm diagnosis](four-arm-diagnosis.json)
and [native](native-four-arm-trace.json.gz) /[Pyodide](pyodide-four-arm-trace.json.gz)
full traces are authoritative; reproduce with `trace_four_arm.mjs OUTDIR`.
The initial two-MPPI-arm traces and diagnosis are retained as preliminary
supporting evidence, superseded for the four-arm maximum. Their first-grid tick
was indexed without accounting for the no-window tick 0; it is tick 3, not 2. This is not accepted as
floating-point noise. The exact origin of the earliest tiny libm differences
was not isolated; the downstream discrete costmap divergence is directly
observed in both runtimes.

No native-equivalence pass is claimed. A candidate continuous-family absolute
numeric tolerance is `1e-9` (excluding timing and runtime-specific hashes),
with exact discrete/status agreement; this fails control today. Localisation's
review maximum `1.1102230246251565e-16` fits that candidate tolerance. Global
planner event columns should agree exactly, excluding timing. These are
proposed contract thresholds, not a newly implemented passing CI gate.
Shipped determinism stays Pyodide on all four engines; state hash stays v2,
and v1/v2 references and goldens are unchanged.

## Deployment gate (TESTED configuration)

A push to main continues to run Lab's build/test jobs. Pages deploy is named
**Deploy site**, depends on all three jobs, and runs only for a manual dispatch
on main with the required confirmation input equal to `DEPLOY`. The truth-table
regression `lab_web/tools/test_deploy_gate.py` passes: push/main cannot satisfy
the deploy expression, even if confirmation is supplied. This verifies the
configuration without pushing to main or deploying. README §9 records that the
public site stays on M4 until Gautham presses the button after the real-phone
and five-person usability gates. No deploy was triggered. The review-branch
workflow dispatched here uses the old workflow and skips deployment by branch.

## Remaining closure work

Open-page asset pinning, waiting-worker notice/export/reload behavior, cache
retention and the update-open-tab-ac3 CI regression remain unimplemented. The
review probe's `openDocumentMixed: true` remains the latest result; no false
claim of a passing probe is made.

Fresh exact-final-head 30-minute soaks on both GPUs, the full review measurement
rerun and a native-versus-Pyodide CI gate remain pending at this explicit report
stop. Earlier acceptance/performance evidence remains historical and is
superseded as an attestation of the eventual closure head, not deleted.

ADB on 2026-10-20 reports no attached device: **Phone not connected**. No real
measurement or usability result is invented. The profile was balanced and AC
online; no robot/simulator batch was active. No M6 worktree was modified. The
sceneCore/Renderer decomposition is recorded as M6 UI's first task; portrait
Compare's horizontal results row is accepted by the owner.
