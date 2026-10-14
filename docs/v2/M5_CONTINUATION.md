Continue COCO Lab M5 · Focus and polish on branch v2/m5-focus, from M5.1.

Read first: README.md, CLAUDE.md, docs/STATUS.md and docs/v2/M5_PROMPT.md. Everything in docs/v2/M5_PROMPT.md still applies, except where this prompt changes it.

1. Gautham's decisions (record each in the plan-change log in docs/STATUS.md, dated 2026-10-14)
The pre-design prerequisite is waived. Gautham explicitly waives README section 7's "3-person test + phone measurement" before M5's design work.
Do not wait for notes.
Carry on through M5.1–M5.11 without stopping for this.
docs/v2/usability/2026-10-pre-m5.md stays as committed (a blank template); record in docs/v2/M5_DESIGN_INPUTS.md that no pre-design observations exist.
The target phone is the Nothing Phone (1). It is Gautham's own phone, and the phone UI is designed for it first (section 2 below). Other phones must still work.
The agent measures the phone. Gautham will not run the phone measurements by hand, so the README M5 "Phone" row moves from Gautham to agent:
On the real phone over USB whenever it is connected with USB debugging on (section 3). This is the only way the row can be marked met.
On an emulated Nothing Phone (1) profile always. Emulated results are labelled "emulated" and never satisfy the row on their own.
If the real phone is never connected during M5, the row stays pending: connect the phone over USB.
The five-person usability test stays Gautham's, and stays a gate for the public v2.0 launch only. It does not block M5's implementation or its pull request.
2. Tailor the phone UI to the Nothing Phone (1)

Verify every hardware fact below on the real device when connected (through window.innerWidth, innerHeight, devicePixelRatio, screen.* and the env(safe-area-inset-*) values), and record what you measure in docs/v2/PHONE_PROFILE.md. Until then, treat the facts as assumptions.

Fact (assumed until measured)	Value
Screen	6.55-inch OLED, 1080 × 2400 px, up to 120 Hz
Chip	Snapdragon 778G+ with an Adreno 642L GPU
Browser	Chrome on Android
CSS viewport	about 412 × 915 in portrait (about 915 × 412 in landscape), devicePixelRatio about 2.625. These change with Android's display-size setting, so the layout must not depend on exact values
Notches and bars	A punch-hole camera in the top-left corner of portrait (left edge in landscape); a gesture bar at the bottom

Design rules for this phone:

Play is landscape and full-screen.
Starting a game requests full-screen and screen.orientation.lock('landscape') where allowed; if refused, show the "rotate your phone" card.
Respect every env(safe-area-inset-*) edge, so nothing sits under the punch-hole or the gesture bar.
Touch layout at about 915 × 412:
Joystick bottom left, 120–140 CSS px across, its dead-zone and travel tuned for thumbs.
Action buttons bottom right as a thumb arc: STOP largest, then Grasp, Autonomy, Camera. Every target at least 48 × 48 CSS px, with at least 8 px between targets.
A slim top strip for the objective and timer.
A minimap of about 96 px at top right.
Text at least 14 CSS px. Nothing else on screen, and the M5 Focus count of 8 controls or fewer applies.
Browser behaviour.
touch-action: none on the play surface; overscroll-behavior: none.
No pull-to-refresh, double-tap zoom or text selection during play.
Pause rendering when the page is hidden.
Frame rate and heat.
On phones the render loop is capped at 60 fps, even on a 120 Hz screen, with a setting to allow 120.
The render pixel ratio is capped by quality tier, about 1.5–2.0 rather than the full 2.625; the default tier is chosen from measured frame time.
The 10-minute heat run in section 3 decides the default cap.
Haptics. A short navigator.vibrate pulse on grasp, contact and delivery. On by default on phones; switchable in Settings; skipped silently where unsupported.
Installable. A web app manifest (name, icons, display: fullscreen, orientation: landscape for Play's start URL, dark theme colour) so "Add to Home screen" opens COCO like a game. The icons are your own work, recorded in the asset manifest.
Compare and Research in portrait (about 412 × 915): stacked top-down panes, a bottom sheet for controls, and the results strip as a swipeable row.
Screenshots. Every look-changing checkpoint commits screenshots of the emulated Nothing Phone (1) in landscape and portrait, as well as desktop.
3. Measuring on the phone
Emulated profile. Add a Playwright device profile, nothing-phone-1, as a shared harness file:
Chrome Android user agent
viewport 412 × 915 (portrait) and 915 × 412 (landscape)
devicePixelRatio 2.625
touch and mobile on
CPU throttled 4× as a stated proxy for the chip
emulated 4G for cold starts
Run every phone check in it. Label all results "emulated Nothing Phone (1)".
The real phone over USB. When the phone is connected with USB debugging on:
Check with adb devices.
Drive Chrome on the phone through the DevTools protocol (adb forward tcp:9222 localabstract:chrome_devtools_remote, then connect Playwright over CDP).
Measure on the phone's own network: first visible computation, 3D world drawn, live model ready, Play's frame rate over 1 and 10 minutes, touch-to-motion latency (from ?perf), and any context loss or reload.
Record the network type, battery level and phone temperature if the system reports it.
Save everything in docs/v2/data/m5/phone/ as "MEASURED on Nothing Phone (1), Chrome <version>".
If adb or the phone is not available, skip this, and say so in STATUS.md and in the final report.
Ask once. At the first look-changing checkpoint (M5.4), add one line to STATUS.md's questions:

Plug in the Nothing Phone (1) with USB debugging on when convenient; the agent measures it automatically.

Do not stop to wait for it.
4. Order of work

Continue in the order of docs/v2/M5_PROMPT.md: M5.1 defects → M5.2 agent overhead → M5.3 code shape → M5.4 design system → M5.5 app shell → M5.6 Play → M5.7 Compare → M5.8 Recordings → M5.9 caching and counter → M5.10 launch drafts → M5.11 measure and pull request. Fold the phone rules from section 2 into M5.4–M5.6 and M5.7, and the measuring from section 3 into M5.11, plus any earlier checkpoint where the phone happens to be connected.

All earlier rules stand:

never merge the pull request
no releases
no destructive git commands
nothing deleted except the committed node_modules/ cache
balanced profile on AC for laptop numbers
emulated results labelled as emulated
stop only on the stop conditions in docs/v2/M5_PROMPT.md

End each session with the final report template from docs/v2/M5_PROMPT.md, with one extra line:

Phone: emulated Nothing Phone (1) results | real-phone results (or "not connected") | phone default settings chosen (frame-rate cap, pixel ratio, tier)
