#!/bin/bash
# Build the 1D site (ee8aace) and serve it on 127.0.0.1:4174 for an A/B fps baseline.
J=/home/gautham/.claude/jobs/eb997671/tmp
T=$J/old_tree
WHEEL="/home/gautham/ros2_ws(personal)/src/coco-robot-ros2/.claude/worktrees/lab1/lab_web/public/generated/py/coco_lab-0.2.0-py3-none-any.whl"
cp "$WHEEL" $J/old_wheel.whl
cd "$T" || exit 1
env -i PATH=/usr/bin:/bin HOME="$HOME" PYTHONPATH="$T/coco_lab" "$J/venv_plain/bin/python" \
  lab_web/tools/build_catalog.py --wheel $J/old_wheel.whl > $J/old_catalog.log 2>&1 || { tail $J/old_catalog.log; exit 1; }
cd "$T/lab_web" || exit 1
export PATH=$J/node-v24.21.0-linux-x64/bin:/usr/bin:/bin
npm ci > $J/old_npm.log 2>&1 || { tail $J/old_npm.log; exit 1; }
npm run build > $J/old_build.log 2>&1 || { tail $J/old_build.log; exit 1; }
for pid in $(pgrep -f "vite previe[w] --port 4174"); do kill "$pid"; done
nohup npx vite preview --port 4174 --strictPort --host 127.0.0.1 > $J/old_preview.log 2>&1 &
for _ in $(seq 1 40); do
  curl -s -o /dev/null http://127.0.0.1:4174/coco-robot-jazzy-2.0/ && { echo "old preview up"; exit 0; }
  sleep 0.25
done
echo "old preview did not start"; exit 1
