# foxglove_bridge: `client_topic_whitelist` is not applied — upstream draft (for Gautham to file)

Prepared 2026-11-28 (R6.A2). **Nothing has been filed.** Gautham files it himself.

## What upstream already has (checked 2026-11-28)

- **foxglove/foxglove-sdk#1508** — "foxglove_bridge: enforce client_topic_whitelist", an **open draft PR** by a
  Foxglove maintainer (gasmith), opened 2026-10-12, last updated 2026-10-14, unmerged. Its description states the
  same defect: *"`client_topic_whitelist` was parsed but never used, so clients could publish on any topic."* It is
  stacked on **#1509** (per-client `sendStatus`, also an open draft) and fixes their internal ticket DB-2022.
  <https://github.com/foxglove/foxglove-sdk/pull/1508>
- **No public GitHub issue** for ROS 2 was found (searched "client_topic_whitelist" across GitHub issues and PRs, and
  "whitelist" in foxglove/foxglove-sdk and foxglove/ros-foxglove-bridge). The closest is
  foxglove/ros-foxglove-bridge#180 (ROS 1, "Topic whitelist is not bidirectional", closed 2023-03-08).

**Suggestion:** since a fix exists as a draft, the most useful thing is a comment on #1508 with the reproduction
below (it shows the released 3.6.3 package is affected and gives a test the fix can be checked against). If a
standalone issue is preferred, the text below works as one; it links #1508.

## Reproduction (verified)

Run in CI on a stock `ros:jazzy-ros-base` container, `ros-jazzy-foxglove-bridge 3.6.3-1noble.20261105.114855`
from the ROS apt repository: workflow `.github/workflows/foxglove-repro.yml`, run
[46108355151](https://github.com/GauthamCodes/coco-labs/actions/runs/46108355151) (log: the `foxglove-repro`
artifact). Files: [`foxglove_repro/repro.sh`](foxglove_repro/repro.sh), [`foxglove_repro/client.py`](foxglove_repro/client.py).
The same defect was first seen in COCO Lab's own image (CI run 45866330520: a client advertising the wheel
command topic made `/foxglove_bridge` a second publisher on it), which is why that image's bridge is read-only.

---

## Ready-to-paste text

**Title:** ROS 2 foxglove_bridge 3.6.3: `client_topic_whitelist` is not applied — clients can publish on any topic

**Body:**

### Description

With `capabilities: [clientPublish]` and a restrictive `client_topic_whitelist`, foxglove_bridge 3.6.3 (ROS 2
Jazzy) still accepts a client advertisement on a topic that does not match the allowlist, creates a ROS publisher
for it, and forwards the client's messages. The parameter appears to be parsed but never checked when a client
advertises or publishes. (Draft PR #1508 describes the same: "`client_topic_whitelist` was parsed but never used".)

This matters for robots where the allowlist is the only thing keeping a remote client off command topics such as
`cmd_vel`.

### Environment

- `ros-jazzy-foxglove-bridge 3.6.3-1noble.20261105.114855` (ROS apt, Ubuntu 24.04), in `ros:jazzy-ros-base`
- WebSocket subprotocol negotiated: `foxglove.sdk.v1`

### Steps to reproduce

```bash
# in a ros:jazzy-ros-base container
apt-get update && apt-get install -y ros-jazzy-foxglove-bridge python3-websockets
source /opt/ros/jazzy/setup.bash
ros2 run foxglove_bridge foxglove_bridge --ros-args -p port:=8765 \
  -p "capabilities:=[clientPublish]" -p "client_topic_whitelist:=['^/allowed$']" &
python3 client.py ws://127.0.0.1:8765 &      # advertises /allowed and /not_allowed, publishes on both for 10 s
sleep 4
ros2 topic info -v /not_allowed               # publisher: foxglove_bridge
ros2 topic echo --once /not_allowed std_msgs/msg/String
```

`client.py` (Python, `websockets`):

```python
import asyncio, json, struct, sys
import websockets

def cdr_string(text):
    data = text.encode() + b'\0'
    return b'\x00\x01\x00\x00' + struct.pack('<I', len(data)) + data

async def main(url):
    async with websockets.connect(url, subprotocols=['foxglove.sdk.v1', 'foxglove.websocket.v1']) as ws:
        await ws.recv()  # serverInfo
        await ws.send(json.dumps({'op': 'advertise', 'channels': [
            {'id': 1, 'topic': '/allowed', 'encoding': 'cdr', 'schemaName': 'std_msgs/msg/String'},
            {'id': 2, 'topic': '/not_allowed', 'encoding': 'cdr', 'schemaName': 'std_msgs/msg/String'}]}))
        await asyncio.sleep(2)
        for _ in range(20):
            for cid, text in ((1, 'to /allowed'), (2, 'to /not_allowed')):
                await ws.send(b'\x01' + struct.pack('<I', cid) + cdr_string(text))
            await asyncio.sleep(0.5)

asyncio.run(main(sys.argv[1]))
```

### Expected

`/not_allowed` does not match `^/allowed$`: the advertisement is refused (ideally with a status message to the
client), no ROS publisher is created, and nothing is published on `/not_allowed`.

### Actual

```text
/allowed: publishers=[foxglove_bridge] received=[data: to /allowed]
/not_allowed: publishers=[foxglove_bridge] received=[data: to /not_allowed]
```

The bridge log shows the advertisement accepted, with no warning:

```text
[foxglove_bridge]: Client ID 1 is advertising "/not_allowed" (std_msgs/msg/String) on channel 2 with encoding "cdr"
[foxglove_bridge]: Advertising new channel 5 for topic "/not_allowed"
```

### Workaround

Leave `clientPublish` out of `capabilities` (the bridge becomes read-only) and send commands through a separate,
restricted path.

### Related

- Draft PR #1508 (enforce `client_topic_whitelist`), stacked on #1509.
