# R4 · Learn: before and after (for Gautham's look review; a soft gate)

Desktop 1440x1000 and the EMULATED Nothing Phone (1) in both orientations (never the real phone; it was not
connected). Before: the live site on 2026-11-10 (main `60c6e1f`). After: the R4 build served locally.

| page | before | after | what changed |
| --- | --- | --- | --- |
| Learn (`?view=learn`) | [desktop](screens/before/desktop-learn.png) · [landscape](screens/before/phone-landscape-learn.png) · [portrait](screens/before/phone-portrait-learn.png) | [desktop](screens/r42/desktop-learn.png) · [landscape](screens/r42/phone-landscape-learn.png) · [portrait](screens/r42/phone-portrait-learn.png) | seven mission cards → the course: three tracks, ten modules with their lessons and stars, the privacy statement |
| a module | — | [M1](screens/r42/desktop-module-1.png) · [M2](screens/r42/desktop-module-2.png) | new: lessons, track chips, stars, the completion-link maker, the guided tour link |
| a lesson: Predict | [tour beat](screens/before/desktop-tour-1-predict.png) | [desktop](screens/r42/desktop-lesson-predict.png) · [landscape](screens/r42/phone-landscape-lesson-predict.png) | the six steps; a wrong pick shows why it is a common misconception |
| Explain | — | [desktop](screens/r42/desktop-lesson-explain.png) · [landscape](screens/r42/phone-landscape-lesson-explain.png) | ≤ 250 words, one SVG diagram (Okabe-Ito), the claims with their evidence labels |
| Try (code) | — | [desktop](screens/r42/desktop-lesson-try-code.png) · [landscape](screens/r42/phone-landscape-lesson-try-code.png) · [portrait](screens/r42/phone-portrait-lesson-try-code.png) | the Studio's editor, Check, hints (recorded), reference solution after a real attempt; "coding is easier on a laptop" on a phone |
| In real ROS 2 | — | [desktop](screens/r42/desktop-lesson-ros2.png) | Nav2's names and defaults (checked sources), STACK evidence |
| Glossary | — | [desktop](screens/r42/desktop-glossary.png) · [portrait](screens/r42/phone-portrait-glossary.png) | 54 terms, ROS 2 terms included |
| Teachers | — | [desktop](screens/r42/desktop-teacher.png) · [landscape](screens/r42/phone-landscape-teacher.png) | assignment links; the class dashboard (paste links, re-verify, CSV) |
| My progress | — | [desktop](screens/r42/desktop-progress.png) | stars, hints, solution viewed; export/import as a file |

The seven guided tours are unchanged (`?view=compare&tour=`; old `?view=learn&mission=` links still open them).

## Looks to judge

1. The Explain step's text column is narrow on a wide screen (72 characters): readable, but the diagram sits below the
   text rather than beside it. Keep, or put the diagram beside the text on desktop?
2. The Try step for code shows the whole starter file (its docstring first): the TODO is at line 18. Scroll the
   editor to the TODO on open?
3. Stars use ★/☆ characters (with a text label for screen readers). Enough, or an icon set?
