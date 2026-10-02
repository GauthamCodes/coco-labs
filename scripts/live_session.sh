#!/usr/bin/env bash
# live_session.sh code|new|kill|status -- the HOST's controls for a remote
# live session (Phase 2 Part C). They are ROS Trigger services on the
# platform node inside the container, reached with `docker exec`; nothing
# that arrives over HTTP or the tunnel can call them.
#
#   code    print the current control code (give it to the driver)
#   new     end the current session (COCO stops) and start one with a new code
#   kill    the kill switch: COCO stops, the session ends, the code is void,
#           every browser is disconnected; `new` starts the next session
#   status  container health and the public /healthz `live` summary
set -o pipefail
CONTAINER="${COCO_CONTAINER:-coco-platform}"
call() {
  docker exec "$CONTAINER" coco-entrypoint \
    ros2 service call "/coco_web_platform/$1" std_srvs/srv/Trigger \
    | grep -E "success=|message=" | sed -E "s/.*success=(True|False), message='([^']*)'.*/\1: \2/"
}
case "${1:-}" in
  code) call session_code ;;
  new) call session_new ;;
  kill) call session_kill ;;
  status)
    docker inspect -f '{{.State.Health.Status}}' "$CONTAINER"
    curl -s "http://127.0.0.1:${COCO_HTTP_PORT:-8080}/healthz" \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("state"), d.get("live"))'
    ;;
  *) sed -n '2,13p' "$0"; exit 2 ;;
esac
