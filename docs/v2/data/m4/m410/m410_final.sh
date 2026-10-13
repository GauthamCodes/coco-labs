#!/usr/bin/env bash
# M4.10, on the final build (7e72010: the replay runs-list fix; /v1/ fetched as CI does): the replays,
# the old URL forms and the console check again, and the long-task observer's self-check. Balanced, AC.
. /home/gautham/coco_lab_m4_ws/bin/env.sh
export PATH="$NODE_BIN:/usr/bin:/bin"
E=/home/gautham/coco_lab_m4_ws/m410
S=http://127.0.0.1:4244/coco-labs/
ORIG=$(powerprofilesctl get)
trap 'powerprofilesctl set "$ORIG"; echo "profile restored to $(powerprofilesctl get)"' EXIT
ac() { cat /sys/class/power_supply/ACAD/online; }
steady_ac() { local ok=0; until [ $ok -ge 30 ]; do if [ "$(ac)" = "1" ]; then ok=$((ok+5)); else ok=0; fi; sleep 5; done; }
if ps aux | grep -Ei 'gz sim|gazebo|isaac|ros2 launch' | grep -v grep >/dev/null; then echo "SIMULATOR RUNNING - abort"; exit 2; fi
cd "$WT/lab_web" || exit 1
echo "final $(date -Is) at $(git -C "$WT" rev-parse --short HEAD)"
step() { local name=$1; shift; steady_ac; powerprofilesctl set balanced; echo "== $name $(date -Is) AC $(ac) load $(cut -d' ' -f1-3 /proc/loadavg)"; "$@"; echo "== $name exit=$? AC $(ac) $(date -Is)"; }
mkdir -p "$E/final"
step replays node tools/perf/replay_check.mjs --site $S --out "$E/final/replays"
step v1_links node tools/perf/v1_links_check.mjs --site $S --out "$E/final/v1_links"
step console node tools/perf/console_check.mjs --site $S --out "$E/final/console"
step longtask_selfcheck node tools/perf/_lt_tmp.mjs "$E/final/longtask_selfcheck.json"
echo "end $(date -Is)"
