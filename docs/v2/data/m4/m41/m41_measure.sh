#!/bin/bash
# M4.1 feasibility measurements: the 3D Arena (follow camera) on the RTX 4050, the Intel iGPU,
# and EMULATED weak devices (phone viewport + 4x / 6x CPU throttling), plus 3D cold start on emulated 4G.
# Balanced profile on AC; restores the profile on exit. Site: the M4 worktree's build on 4244.
. /home/gautham/coco_lab_m4_ws/bin/env.sh
export PATH="$NODE_BIN:/usr/bin:/bin"
OUT=/home/gautham/coco_lab_m4_ws/logs/m41
S=http://127.0.0.1:4244/coco-labs/
ORIG=$(powerprofilesctl get)
restore() { powerprofilesctl set "$ORIG"; echo "profile restored to $(powerprofilesctl get)"; }
trap restore EXIT
steady_ac() { local ok=0; until [ $ok -ge 30 ]; do if [ "$(cat /sys/class/power_supply/ACAD/online)" = "1" ]; then ok=$((ok+5)); else ok=0; fi; sleep 5; done; }
if ps aux | grep -Ei 'gz sim|gazebo|isaac|ros2 launch' | grep -v grep >/dev/null; then echo "SIMULATOR RUNNING - abort"; exit 2; fi
curl -sf "$S" > /dev/null || { echo "site not served - abort"; exit 2; }
steady_ac
powerprofilesctl set balanced
sleep 20
mkdir -p $OUT
echo "start $(date -Is): profile $(powerprofilesctl get) AC 1 load $(cut -d' ' -f1-3 /proc/loadavg) driver $(nvidia-smi --query-gpu=driver_version --format=csv,noheader) mesa $(dpkg-query -W -f='${Version}' mesa-vulkan-drivers 2>/dev/null)"
cd "$WT/lab_web" || exit 1
# AC comes and goes on this laptop: wait until it has been on for 30 s before each run, and keep a
# run only if its own recorded conditions say AC at its start AND end (else it is run again).
run() {
  local name=$1; shift
  for attempt in 1 2 3 4 5 6; do
    steady_ac
    node tools/perf/render3d_fps.mjs --site $S --out $OUT/$name.json "$@" 2>&1 | tail -1 | sed "s/^/$name: /"
    python3 -c "import json,sys; c=json.load(open(sys.argv[1]))['conditions']; sys.exit(0 if c['start']['ac_power'] and c['end']['ac_power'] else 1)" $OUT/$name.json && return
    echo "$name: AC dropped during the run (attempt $attempt), run again"; mv $OUT/$name.json $OUT/$name.battery_$attempt.json
  done
}
for i in 1 2 3; do run nvidia_follow_$i --gpu nvidia --camera follow --seconds 20; done
run nvidia_orbit_1 --gpu nvidia --camera orbit --seconds 20
run nvidia_robot_eye_1 --gpu nvidia --camera robot_eye --seconds 20
run nvidia_topdown_1 --gpu nvidia --camera topdown --seconds 20
for i in 1 2 3; do run nvidia_follow_m2_$i --gpu nvidia --camera follow --scene m2 --seconds 20; done
for i in 1 2 3; do run intel_follow_$i --gpu intel --camera follow --seconds 20; done
for i in 1 2; do run intel_follow_m2_$i --gpu intel --camera follow --scene m2 --seconds 20; done
run intel_topdown_1 --gpu intel --camera topdown --seconds 20
for c in 4 6; do for i in 1 2; do run emulated_phone_intel_cpu${c}_follow_$i --gpu intel --phone 1 --cpu $c --camera follow --seconds 20; done; done
run emulated_phone_intel_cpu6_topdown_1 --gpu intel --phone 1 --cpu 6 --camera topdown --seconds 20
for i in 1 2 3; do run emulated_4g_nvidia_follow_$i --gpu nvidia --net 4g --camera follow --seconds 3; done
echo "end $(date -Is): AC $(cat /sys/class/power_supply/ACAD/online) load $(cut -d' ' -f1-3 /proc/loadavg)"
