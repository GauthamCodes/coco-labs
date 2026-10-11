#!/bin/bash
# Review A.2.9: M3's four outstanding M2 budgets, re-measured on the review build
# (fresh clone at 7052aa8, served on 4224 with /v1/), GPU, balanced on AC, n >= 10.
# Restores the original power profile on exit.
. /home/gautham/review/bin_m3/env.sh
export PATH="$NODE_BIN:/usr/bin:/bin"
OUT=$M1/logs/remeasure
SITE=http://127.0.0.1:4224/coco-labs/
ORIG=$(powerprofilesctl get)
restore() { powerprofilesctl set "$ORIG"; echo "profile restored to $(powerprofilesctl get)"; }
trap restore EXIT
[ "$(cat /sys/class/power_supply/ACAD/online)" = "1" ] || { echo "NOT ON AC - abort"; exit 2; }
if ps aux | grep -Ei 'gz sim|gazebo|isaac|ros2 launch' | grep -v grep >/dev/null; then echo "SIMULATOR RUNNING - abort"; exit 2; fi
curl -sf "$SITE" > /dev/null || { echo "site not served on 4224 - abort"; exit 2; }
powerprofilesctl set balanced
sleep 20
mkdir -p $OUT/render $OUT/responsiveness $OUT/seek $OUT/coldstart $OUT/gpu
echo "start $(date -Is): profile $(powerprofilesctl get) AC $(cat /sys/class/power_supply/ACAD/online) battery $(cat /sys/class/power_supply/BAT1/capacity)% governor $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor) load $(cut -d' ' -f1-3 /proc/loadavg) driver $(nvidia-smi --query-gpu=driver_version --format=csv,noheader)"
ac() { [ "$(cat /sys/class/power_supply/ACAD/online)" = "1" ] || { echo "AC LOST - abort"; exit 3; }; }
node /home/gautham/review/bin_m3/gpu_probe.mjs $OUT/gpu/gpu_probe_start.json > /dev/null && echo "gpu probe start ok"
cd "$WT/lab_web" || exit 1
for i in $(seq 1 10); do
  ac; node tools/perf/render_fps.mjs --site $SITE --gl gpu --seconds 10 --out $OUT/render/fps_m1_gpu_$i.json 2>&1 | tail -1 | sed "s/^/m1 $i: /"
done
ac; node tools/perf/responsiveness.mjs --site $SITE --out $OUT/responsiveness --n 25 --gpu 1 --immediate 1 2>&1 | tail -1
for i in 1 2 3; do
  ac; mkdir -p $OUT/seek/run_$i; node tools/perf/seek_check.mjs --site $SITE --out $OUT/seek/run_$i --gpu 1 2>&1 | tail -1 | sed "s/^/seek $i: /"
done
ac; node tools/perf/coldstart.mjs --site $SITE --runs 10 --pyodide self --throttle 4g --gl gpu --out $OUT/coldstart/review_4g_gpu.json 2>&1 | tail -1 | sed "s/^/4g: /"
node /home/gautham/review/bin_m3/gpu_probe.mjs $OUT/gpu/gpu_probe_end.json > /dev/null && echo "gpu probe end ok"
echo "end $(date -Is): profile $(powerprofilesctl get) AC $(cat /sys/class/power_supply/ACAD/online) load $(cut -d' ' -f1-3 /proc/loadavg)"
