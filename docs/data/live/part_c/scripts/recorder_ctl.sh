#!/usr/bin/env bash
# recorder_ctl.sh start|stop OUT_DIR -- the ROS recorder (wheel topic,
# arbiter inputs, modes, mission state, /plan, /goal_pose, ground truth,
# wheel-publisher count; wall clock) inside the running coco-platform
# container, for a live session on an already-running stack.
HERE="$(cd "$(dirname "$0")" && pwd)"
case "${1:-}" in
  start)
    docker cp "$HERE/recorder.py" coco-platform:/tmp/recorder.py
    docker exec coco-platform rm -f /tmp/ros.jsonl
    docker exec -d coco-platform bash -c \
      'source /opt/ros/jazzy/setup.bash; source /opt/coco_ws/install/setup.bash; exec python3 /tmp/recorder.py /tmp/ros.jsonl'
    sleep 3
    docker exec coco-platform pgrep -f 'recorder.p[y]' >/dev/null && echo "recorder running"
    ;;
  stop)
    docker exec coco-platform pkill -INT -f 'recorder.p[y]'
    sleep 1
    docker cp coco-platform:/tmp/ros.jsonl "$2/ros.jsonl"
    docker cp coco-platform:/tmp/coco_stack.log "$2/stack.log"
    docker logs coco-tunnel > "$2/tunnel.log" 2>&1
    echo "copied to $2"
    ;;
  *) sed -n '2,5p' "$0"; exit 2 ;;
esac
