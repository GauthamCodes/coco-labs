# R2.5 · Share links — TESTED

- **Code links** (`lab_web/src/studio/codelink.ts`): the file, its name, the suite and scenario are deflate-compressed
  into the URL **fragment**, `#code=<base64url>` (a fragment never reaches a server). Past 64 KB of link the Studio
  refuses with "links carry at most 64 KB. Download the .py and share the file instead." A damaged or foreign link is
  refused; file names are sanitised.
- **Consent** (ADR 0012): opening a code link (or a leaderboard entry, `&entry=<suite>/<name>`) shows the code with a
  banner — "This link carries code someone else wrote" — and a **Run this code** button. Until it is pressed, Run,
  Compare, Benchmark and Export are disabled and the sandbox is not started; nothing runs automatically; a stranger's
  code is not written into the reader's draft.
- **Download / upload `.py`**: Download saves the editor's file; Upload reads a `.py` (≤ 256 KB) into the editor without
  running it.

Evidence: `lab_web/test/r2_studio.test.ts` (round trip exact; the 64 KB refusal; foreign/damaged fragments; name
sanitising) and `studio_check.mjs` in a real browser (a 2,359-character link of the pure-pursuit starter opened in a
fresh context: code shown, Run disabled, no request for the sandbox worker before consent, enabled after). Upload is
exercised by every escape and Studio check (each file is uploaded through the page).

Experiment links that include an algorithm file (R1's `?exp=`/`#expz=` carrying code) are not built: the Studio's
code link carries the file and its scenario, and an experiment with it is one button away. Recorded as a deviation.
