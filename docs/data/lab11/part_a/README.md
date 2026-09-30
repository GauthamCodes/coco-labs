# Lab 1.1 Part A — browser evidence (2026-10-01)

Measured in headless Firefox 156.0.1 with `lab_web/tools/browser/check.py`
against the local production build (`vite preview`, 127.0.0.1:4173).

- `browser_report.json`: every scenario (smoke, player, reduced, fps,
  phone, weight, edit, lab) on the final Part A build; load average
  1.0–1.7.
- `lab_*.png`, `phone_390x844_player.png`: screenshots from that run.
- `fps_ab/`: the playback A/B.
  - `before_fix_new_*.json`: three Part A samples before the fix (the swept
    footprint was rendered lazily inside a playback frame).
  - `after_fix_{old,new}_*.json`: interleaved samples after the fix; `old`
    is the 1D site built from `ee8aace` and served on :4174, `new` is Part
    A.
- `fps_ab/fps_ab.sh` and `fps_ab/old_build.sh`: the scripts as run. They
  use the session's job-local paths (`~/.claude/jobs/…`), so they are a
  record, not a tool; `docs/RESULTS.md` "COCO Lab 1.1, Part A" gives the
  method.
