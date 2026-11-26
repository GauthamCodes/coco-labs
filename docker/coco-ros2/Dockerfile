# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
#
# ghcr.io/gauthamcodes/coco-ros2 -- R5.1: COCO's ROS 2 stack, headless, for LIVE ROS 2 in the browser.
#
#   docker run --rm -p 8765:8765 -p 8766:8766 ghcr.io/gauthamcodes/coco-ros2 --level depot
#
# ROS 2 Jazzy (ros-base), Gazebo Harmonic as a server only (no GUI; software OpenGL through Xvfb for
# the GPU LiDAR and the camera), Nav2, COCO's stack built from THIS repository's packages
# (gazebo_models, custom_teleop with cmd_vel_arbiter, coco_config, coco_sim; never the COCO robot
# repository), foxglove_bridge on 8765 (READ-ONLY), COCO's coco.v1 control gateway (coco_web's
# platform_server, remote mode) on 8766, and COCO Lab's generated levels. Built, tested and measured in
# CI (.github/workflows/coco-ros2-image.yml) before anyone pulls it; docs/DOCKER.md, "coco-ros2".
#
# Kept out, to stay far below the 8.18 GB appliance (/Dockerfile: osrf/ros:jazzy-desktop, MoveIt,
# CPU torch): the desktop variant, MoveIt, torch and the RL climb, the mission executive, perception
# and web_video_server. coco_web runs in remote mode (/ws and /healthz only), with OpenCV's headless
# wheel instead of Ubuntu's python3-opencv (its GUI stack would not fit the size budget). The arm's controllers still load (full_world_robo
# spawns them); nothing here plans arm motions.
#
# Build context: the repository root.
#   docker build -f docker/coco-ros2/Dockerfile --build-arg GIT_SHA=$(git rev-parse HEAD) -t coco-ros2 .

ARG ROS_IMAGE=ros:jazzy-ros-base-noble
# The interpreter and PyYAML the leaderboard verifier already pins (tools/r2/verifier.Dockerfile);
# the level files' checksums do not depend on it (the build fails if they differ).
ARG PY_IMAGE=python:3.12.3-slim-bookworm

# ---- 1. the levels: generated here, never committed; checked against the committed checksums ----
FROM ${PY_IMAGE} AS levels
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
RUN pip install --no-cache-dir PyYAML==6.0.1
WORKDIR /src
COPY coco_lab/coco_lab coco_lab/coco_lab
COPY tools/m6/gen_level.py tools/m6/gen_level.py
COPY worlds worlds
COPY gazebo_models/worlds/coco_navigation.world gazebo_models/worlds/coco_navigation.world
COPY gazebo_models/config/nav2_params.yaml gazebo_models/config/nav2_params.yaml
COPY gazebo_models/urdf/coco_controllers.yaml gazebo_models/urdf/coco_controllers.yaml
COPY docs/v2/g2/data/g29/coco_depot_v1_outputs_d5.json docs/v2/g2/data/g29/coco_depot_colours_v1_outputs_d5.json docs/v2/g2/data/g29/
COPY docs/v2/r3/data/r34/sessions/depot-clutter-50_plan_rep1/meta.json docs/v2/r3/data/r34/sessions/depot-clutter-50_plan_rep1/meta.json
COPY docker/coco-ros2/levels.json docker/coco-ros2/gen_levels.py docker/coco-ros2/
RUN python -P docker/coco-ros2/gen_levels.py /src /opt/coco/levels

# ---- 2. COCO's overlay, built from this repository's packages ----
FROM ${ROS_IMAGE} AS overlay
WORKDIR /opt/coco_ws
COPY coco_config src/coco-labs/coco_config
COPY coco_sim src/coco-labs/coco_sim
COPY custom_teleop src/coco-labs/custom_teleop
COPY gazebo_models src/coco-labs/gazebo_models
COPY coco_web src/coco-labs/coco_web
# BUILD_TESTING off: the tests run in CI's ROS job (ci.yml); the image needs none of their deps.
RUN . /opt/ros/jazzy/setup.sh \
 && colcon build --packages-select coco_config coco_sim custom_teleop gazebo_models coco_web \
      --cmake-args -DBUILD_TESTING=OFF --event-handlers console_cohesion+

# ---- 3. the runtime ----
FROM ${ROS_IMAGE}
ENV DEBIAN_FRONTEND=noninteractive
# Each package is the minimum the four launch files need (gazebo_models full_world_robo.launch.py and
# nav.launch.py, custom_teleop arbiter.launch.py) plus the bridge, CycloneDDS and software OpenGL.
# navigation2: every Nav2 plugin COCO's parameters and the R3 variants name (Smac 2D/Hybrid, NavFn,
# DWB, Regulated Pure Pursuit, MPPI, the rotation shim, docking).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ros-jazzy-ros-gz-sim \
      ros-jazzy-ros-gz-bridge \
      ros-jazzy-gz-ros2-control \
      ros-jazzy-controller-manager \
      ros-jazzy-ros2controlcli \
      ros-jazzy-diff-drive-controller \
      ros-jazzy-joint-state-broadcaster \
      ros-jazzy-joint-trajectory-controller \
      ros-jazzy-robot-state-publisher \
      ros-jazzy-xacro \
      ros-jazzy-navigation2 \
      ros-jazzy-nav2-bringup \
      ros-jazzy-rmw-cyclonedds-cpp \
      ros-jazzy-foxglove-bridge \
      xvfb \
      libgl1-mesa-dri \
      libglx-mesa0 \
      tini \
      ros-jazzy-std-srvs \
      ros-jazzy-trajectory-msgs \
      python3-tornado \
      python3-numpy \
      python3-pip \
 && python3 -m pip install --no-cache-dir --break-system-packages --no-deps opencv-python-headless==4.10.0.84 \
 && python3 -c "import cv2, numpy, tornado; print('cv2', cv2.__version__, 'numpy', numpy.__version__, 'tornado', tornado.version)" \
 && apt-get purge -y python3-pip && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY --from=overlay /opt/coco_ws/install /opt/coco_ws/install
COPY --from=levels /opt/coco/levels /opt/coco/levels
COPY docker/coco-ros2/entrypoint.sh /opt/coco/bin/coco-ros2
COPY docker/coco-ros2/level_env.py docker/coco-ros2/check.py docker/coco-ros2/odom_relay.py /opt/coco/bin/
COPY docker/coco-ros2/foxglove_bridge.yaml /opt/coco/config/foxglove_bridge.yaml
ARG GIT_SHA=unknown
RUN chmod 0755 /opt/coco/bin/* \
 && ln -s /opt/coco/bin/coco-ros2 /usr/local/bin/coco-ros2 \
 && printf '{"image": "ghcr.io/gauthamcodes/coco-ros2", "git_sha": "%s", "dockerfile": "docker/coco-ros2/Dockerfile"}\n' \
      "${GIT_SHA}" > /opt/coco/image.json \
 && dpkg-query -W -f '${Package} ${Version}\n' > /opt/coco/packages.txt

# COCO's single-machine settings, as setup_env.sh: CycloneDDS and gz-transport on loopback. The ROS
# graph stays inside the container; only the bridge's port is published.
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    CYCLONEDDS_URI="<CycloneDDS><Domain><General><Interfaces><NetworkInterface name='lo' multicast='true'/></Interfaces></General></Domain></CycloneDDS>" \
    GZ_IP=127.0.0.1 \
    GZ_VERSION=harmonic \
    LIBGL_ALWAYS_SOFTWARE=1 \
    COCO_BRIDGE_PORT=8765 \
    COCO_GATEWAY_PORT=8766

LABEL org.opencontainers.image.source="https://github.com/GauthamCodes/coco-labs" \
      org.opencontainers.image.description="COCO's ROS 2 stack (Jazzy, Gazebo Harmonic headless, Nav2, cmd_vel_arbiter) with a read-only foxglove_bridge on 8765 and the coco.v1 control gateway on 8766, for COCO Lab's LIVE view. A simulation; never hardware." \
      org.opencontainers.image.licenses="Apache-2.0"

EXPOSE 8765 8766
# Ready = every Nav2 lifecycle node active and AMCL publishing (the entrypoint writes the file then).
# The start period covers Gazebo's start under software rendering on a small CPU.
HEALTHCHECK --interval=10s --timeout=5s --start-period=600s --retries=3 \
  CMD test -f /tmp/coco/ready.json || exit 1
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/coco/bin/coco-ros2"]
CMD ["--level", "depot"]
