#!/bin/bash
# Minimal reproduction: foxglove_bridge (ROS 2 Jazzy) does not apply client_topic_whitelist.
#
#   docker run --rm -v "$PWD:/repro" ros:jazzy-ros-base bash /repro/repro.sh
#
# Starts foxglove_bridge with capabilities [clientPublish] and client_topic_whitelist ['^/allowed$'], runs
# client.py (advertises /allowed and /not_allowed, publishes on both), and reports, for each topic, the ROS
# publishers `ros2 topic info -v` lists and whether `ros2 topic echo --once` receives a message.
# Expected: /not_allowed has no publisher and receives nothing. Exit 1 when the allowlist is NOT applied.
set -u
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null
apt-get install -y -qq --no-install-recommends ros-jazzy-foxglove-bridge python3-websockets >/dev/null
source /opt/ros/jazzy/setup.bash
VERSION=$(dpkg-query -W -f '${Version}' ros-jazzy-foxglove-bridge)
echo "ros-jazzy-foxglove-bridge $VERSION"
DIR=$(cd "$(dirname "$0")" && pwd)

ros2 run foxglove_bridge foxglove_bridge --ros-args -p port:=8765 \
  -p "capabilities:=[clientPublish]" -p "client_topic_whitelist:=['^/allowed$']" > /tmp/bridge.log 2>&1 &
BRIDGE=$!
sleep 5

python3 "$DIR/client.py" ws://127.0.0.1:8765 > /tmp/client.log 2>&1 &
CLIENT=$!
sleep 4                                          # advertised; the client publishes for 10 s
result=0
for topic in /allowed /not_allowed; do
  pubs=$(ros2 topic info -v "$topic" 2>/dev/null | awk '/^Node name:/ {n=$3} /^Endpoint type: PUBLISHER/ {print n}' | tr '\n' ' ')
  got=$(timeout 4 ros2 topic echo --once "$topic" std_msgs/msg/String 2>/dev/null | grep -o "data: .*" | head -1)
  echo "$topic: publishers=[${pubs% }] received=[${got:-nothing}]"
  if [ "$topic" = /not_allowed ] && { [ -n "$pubs" ] || [ -n "$got" ]; }; then result=1; fi
done
wait $CLIENT
echo "--- client"; cat /tmp/client.log
echo "--- bridge log (whitelist / advertise lines)"; grep -iE "whitelist|advertis|not allowed|reject" /tmp/bridge.log | head -20
kill $BRIDGE 2>/dev/null
if [ $result -eq 1 ]; then
  echo "REPRODUCED: a client published on /not_allowed despite client_topic_whitelist ['^/allowed\$'] ($VERSION)"
else
  echo "NOT REPRODUCED: /not_allowed was refused ($VERSION)"
fi
exit $result
