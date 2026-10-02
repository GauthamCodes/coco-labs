#!/usr/bin/env bash
# image_check.sh: which image and base the compose service runs, and that
# the Part B / safety code is inside it (not an older layer).
docker image ls --digests | grep -E 'REPOSITORY|coco-platform|osrf'
docker image inspect coco-platform:jazzy --format 'image {{.Id}} created {{.Created}}'
docker run --rm --entrypoint bash coco-platform:jazzy -c '
  S=/opt/coco_ws/src/coco-labs
  echo "nav.local_path in platform_server: $(grep -c local_path $S/coco_web/coco_web/platform_server.py)"
  echo "stop_latch.py present: $(test -f $S/coco_web/coco_web/stop_latch.py && echo yes || echo no)"
  echo "executive _mission_running refs: $(grep -c _mission_running $S/coco_mission/scripts/mission_executive.py)"
  echo "tornado: $(python3 -c "import tornado; print(tornado.version, tornado.__file__)")"
  . /opt/ros/jazzy/setup.sh; echo "ros distro: $ROS_DISTRO"; dpkg -s ros-jazzy-navigation2 | grep ^Version'
