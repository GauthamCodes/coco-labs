# Lab 2 demo video

Two recordings exist, both made in headless Firefox (viewport only) by
`lab_web/tools/browser/record_lab2_demo.py`, with the same script and the
same captions (added by the recorder; they are not part of the site). One
cut in each: the one-time Pyodide start-up and a warm-up run, before
recording began. 0 console errors in both.

| | public site (the release asset) | local build (the first recording) |
|---|---|---|
| site | `https://gauthamcodes.github.io/coco-labs/` (deployed from `4405065`) | `http://127.0.0.1:4173/coco-labs/` (`vite preview` of branch `lab2`) |
| recorded | 2026-10-04, after `main` was fast-forwarded to `4405065` | 2026-10-04, before deployment |
| span / frames captured | 91.76 s / 3,440 | 91.62 s / 3,323 |
| cut | 10.56 s | 10.05 s |
| encoded | H.264, 1120 × 920, 30 fps, 92.8 s, 3,399,232 B | H.264, 1120 × 920, 30 fps, 92.6 s, 3,418,699 B |
| sha256 | `b13aa1feb3f90cc4ff1a25ad2111aeef7c23c8ce47e541cbff15ca687429b648` | `7dd0467382618e5bfad52c96dba11e253dc2a8c275cc263c075e6ad37b9951fb` |
| provenance | `cuts_public.json` | `cuts.json` |
| on this machine | `~/coco_lab_runs/lab2/video_public/coco_lab2_demo.mp4` | `~/coco_lab_runs/lab2/video/coco_lab2_demo.mp4` |

The public-site recording is the one meant for the `lab2-v1.0` release, so
the asset shows the deployed lab rather than a local build. Neither file is
in git (3.4 MB each); as with Lab 1's video, it belongs to a release, which
is the owner's call.
