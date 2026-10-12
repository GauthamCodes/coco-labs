#!/usr/bin/env bash
# M4.10 resume (2026-10-13), on the build with the z= link fix (62f6338): run 1 of the RTX high tier
# re-taken (the first overlapped a pytest run); the race and every step after it.
. /home/gautham/coco_lab_m4_ws/bin/env.sh
export PATH="$NODE_BIN:/usr/bin:/bin"
E=/home/gautham/coco_lab_m4_ws/m410
S=http://127.0.0.1:4244/coco-labs/
WK="$HOME/coco_lab_m2_ws/bin/webkit_mesa.sh"
WKLIB="$HOME/coco_lab_m1_ws/webkit_libs/root/usr/lib/x86_64-linux-gnu"
ORIG=$(powerprofilesctl get)
restore() { powerprofilesctl set "$ORIG"; echo "profile restored to $(powerprofilesctl get)"; }
trap restore EXIT
ac() { cat /sys/class/power_supply/ACAD/online; }
steady_ac() { local ok=0; until [ $ok -ge 30 ]; do if [ "$(ac)" = "1" ]; then ok=$((ok+5)); else ok=0; fi; sleep 5; done; }
if ps aux | grep -Ei 'gz sim|gazebo|isaac|ros2 launch' | grep -v grep >/dev/null; then echo "SIMULATOR RUNNING - abort"; exit 2; fi
curl -sf "$S" > /dev/null || { echo "site not served - abort"; exit 2; }
cd "$WT/lab_web" || exit 1
echo "resume $(date -Is) at $(git -C "$WT" rev-parse --short HEAD) driver $(nvidia-smi --query-gpu=driver_version --format=csv,noheader) mesa $(dpkg-query -W -f='${Version}' mesa-vulkan-drivers 2>/dev/null)"
step() {
  local name=$1; shift
  for attempt in 1 2 3 4; do
    steady_ac
    powerprofilesctl set balanced
    local lost=0
    ( while sleep 2; do [ "$(ac)" = "1" ] || touch "$E/.lost_$name"; done ) & local watch=$!
    rm -f "$E/.lost_$name"
    echo "== $name attempt $attempt $(date -Is) load $(cut -d' ' -f1-3 /proc/loadavg)"
    "$@"; local code=$?
    kill $watch 2>/dev/null; wait $watch 2>/dev/null
    [ -f "$E/.lost_$name" ] && lost=1
    echo "== $name exit=$code ac_lost=$lost $(date -Is)"
    [ $lost -eq 0 ] && return
    echo "== $name: AC was lost during the run; run again"
  done
}
fps() { local n=$1; shift; node tools/perf/render3d_fps.mjs --site $S --out "$E/fps/$n.json" "$@" 2>&1 | tail -1; }
step fps_nvidia_high_m2_1b fps nvidia_high_m2_1b --gpu nvidia --camera follow --scene m2 --quality high --seconds 30
mkdir -p "$E/race_superseded"
mv "$E/race"/* "$E/race_superseded/" 2>/dev/null
step race_score node tools/perf/play_verify.mjs score --site $S --subs "$WT/docs/v2/data/m4/m48/race_submissions.json" --out "$E/race" --gpu 1
step race_chromium node tools/perf/play_verify.mjs reproduce --site $S --out "$E/race" --browser chromium
step race_firefox node tools/perf/play_verify.mjs reproduce --site $S --out "$E/race" --browser firefox
step race_webkit env LD_LIBRARY_PATH="$WKLIB" node tools/perf/play_verify.mjs reproduce --site $S --out "$E/race" --browser webkit --webkit-exe "$WK"
step race_verify node tools/coco.mjs verify --file "$E/race/links.json" --out "$E/race/verify_node.json"
step v1_links node tools/perf/v1_links_check.mjs --site $S --out "$E/v1_links"
step replays node tools/perf/replay_check.mjs --site $S --out "$E/replays"
step modes node tools/perf/modes_check.mjs --site $S --out "$E/modes" --gpu 1
step console node tools/perf/console_check.mjs --site $S --out "$E/console"
step layout node tools/perf/layout_check.mjs --site $S --out "$E/layout"
step soak node tools/perf/soak3d.mjs --site $S --out "$E/soak" --minutes 30 --gpu nvidia
step terrain_shots node tools/perf/terrain_shots.mjs --site $S --out "$E/screens/terrain"
step reference_shots node tools/perf/reference_shots.mjs --site $S --out "$E/screens/reference"
echo "end $(date -Is)"
