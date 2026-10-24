#!/usr/bin/env bash
# G2: every suite on the laptop, in CI's order where CI has one (G1.13's runner, kept in the repo).
# Each step prints "STEP <name> rc=<n> <last log line>"; full logs go to OUT/<name>.log.
#
#   tools/g2/suites.sh OUT_DIR
#
# Environment (defaults are the G2 laptop's):
#   G2_VENV  python of a venv with CI's pins (coco_lab is reinstalled into it from this tree)
#   COCO_WS  ROS overlay built by scripts/build_overlay.sh from this tree
#   G2_PORT  port for tools/perf/serve_dist.mjs (4184: G1's server may still hold 4174)
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V="${G2_VENV:-$HOME/coco_labs_ws/g2_venv/bin/python}"
WS="${COCO_WS:-$HOME/coco_lab_g2_ws}"
PORT="${G2_PORT:-4184}"
L="$(mkdir -p "${1:?usage: suites.sh OUT_DIR}" && cd "$1" && pwd)"
SITE="http://127.0.0.1:$PORT/coco-labs/"
export PATH=/home/gautham/coco_v2_ws/node/node-v24.21.0-linux-x64/bin:$PATH
export PYTHONDONTWRITEBYTECODE=1
step() { local n="$1"; shift; ( "$@" ) > "$L/$n.log" 2>&1; local rc=$?; echo "STEP $n rc=$rc $(tail -1 "$L/$n.log" | cut -c1-200)"; }
echo "# G2 suites $(date -u +%FT%TZ), tree $(git -C "$R" rev-parse --short HEAD)$(git -C "$R" diff --quiet || echo ' + uncommitted')"
echo "# machine: $(powerprofilesctl get 2>/dev/null), AC $(cat /sys/class/power_supply/AC*/online 2>/dev/null), $(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null), Node $(node -v), $($V -V)"
cd "$R"
SRC="$L/coco_lab_src"
rm -rf "$SRC" && cp -r coco_lab "$SRC"
step venv_install env -u PYTHONPATH python3 -m pip --python "$V" install -q --no-deps --force-reinstall "$SRC"
step coco_lab_venv bash -c "cd coco_lab && env -u PYTHONPATH $V -P -m pytest -q -p no:cacheprovider -m 'not gz' --ignore=test/test_copyright.py --ignore=test/test_flake8.py --ignore=test/test_pep257.py --junitxml=$L/coco_lab.xml"
step coco_lab_gz bash -c "source /opt/ros/jazzy/setup.bash && cd coco_lab && env -u PYTHONPATH $V -P -m pytest -q -p no:cacheprovider -m gz --ignore=test/test_copyright.py --ignore=test/test_flake8.py --ignore=test/test_pep257.py"
step lab_web_tools bash -c "env -u PYTHONPATH $V -P -m pytest -q -p no:cacheprovider lab_web/tools --junitxml=$L/tools.xml"
step build_catalog bash -c "env -u PYTHONPATH $V lab_web/tools/build_catalog.py | tail -3"
step schemas_check python3 coco_schemas/scripts/generate.py --lang ts --check
cd lab_web
step typecheck npm run typecheck
step arena_assets npm run arena-assets
step vitest npx vitest run
step native_gate env -u PYTHONPATH node tools/g1/native_gate.mjs --python "$V" --out "$L/native_gate.json"
step coco_verify bash -c "node tools/coco.mjs verify --file ../docs/v2/data/m3/m36/links.json && node tools/play_reference_check.mjs"
step build_twice bash -c 'npm run build >/dev/null && first=$(node tools/check_dist.mjs | node -e "let s=\"\";process.stdin.on(\"data\",d=>s+=d).on(\"end\",()=>console.log(JSON.parse(s).tree_sha256))") && npm run build >/dev/null && node tools/check_dist.mjs --expect-hash "$first" | tail -3'
step fetch_v1 env PYTHON="$V" tools/fetch_v1_site.sh dist/v1
step update_isolation node tools/update_isolation_check.mjs dist "$L/update-isolation"
node tools/perf/serve_dist.mjs --port "$PORT" > "$L/serve.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
sleep 1
WEBKIT=$HOME/coco_lab_m1_ws/bin/webkit_run.sh
step det_v1_10 bash -c 'rec=../docs/v2/data/m1/determinism; for b in chromium firefox webkit; do node tools/perf/determinism.mjs $b --sessions $rec/sessions.json --limit 10 --site '"$SITE"' --out '"$L"'/det --webkit-exe '"$WEBKIT"' || exit 1; done; node tools/perf/determinism.mjs compare --sessions $rec/sessions.json --limit 10 --ref $rec --out '"$L"'/det'
step det_terrain bash -c 'rec=../docs/v2/data/m4/m43/determinism; for b in chromium firefox webkit; do node tools/perf/determinism.mjs $b --sessions $rec/sessions.json --limit 3 --site '"$SITE"' --out '"$L"'/det_terrain --webkit-exe '"$WEBKIT"' || exit 1; done; node tools/perf/determinism.mjs compare --sessions $rec/sessions.json --limit 3 --ref $rec --out '"$L"'/det_terrain'
step screenshots node tools/perf/screenshots.mjs check --site "$SITE" --out "$L/shots"
step chase_hud node tools/g1/chase_hud_check.mjs "$SITE" "$L/chase_hud.json"
step v1_links node tools/perf/v1_links_check.mjs --site "$SITE" --out "$L/v1links"
step replays node tools/perf/replay_check.mjs --site "$SITE" --out "$L/replays"
cd "$R"
step packages env -u PYTHONPATH -u AMENT_PREFIX_PATH -u CMAKE_PREFIX_PATH COCO_WS="$WS" NODE_OPTIONS=--test-reporter=tap ROS_DOMAIN_ID=78 scripts/run_all_package_tests.sh
echo SUITES DONE
