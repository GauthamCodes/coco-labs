#!/usr/bin/env python3
"""Minimal Foxglove WebSocket client: advertise two topics and publish one std_msgs/String on each.

foxglove_bridge runs with client_topic_whitelist ['^/allowed$']. Expected: the bridge refuses the
advertisement of /not_allowed (no ROS publisher, an error status). Usage: client.py ws://127.0.0.1:8765
"""
import asyncio
import json
import struct
import sys

import websockets


def cdr_string(text: str) -> bytes:
    """std_msgs/msg/String in CDR: encapsulation header, uint32 length (with the NUL), bytes, NUL."""
    data = text.encode() + b'\0'
    return b'\x00\x01\x00\x00' + struct.pack('<I', len(data)) + data


async def main(url: str) -> None:
    async with websockets.connect(url, subprotocols=['foxglove.sdk.v1', 'foxglove.websocket.v1']) as ws:
        print('subprotocol', ws.subprotocol, flush=True)
        info = json.loads(await ws.recv())
        print('serverInfo capabilities', info.get('capabilities'), flush=True)
        channels = [{'id': 1, 'topic': '/allowed', 'encoding': 'cdr', 'schemaName': 'std_msgs/msg/String'},
                    {'id': 2, 'topic': '/not_allowed', 'encoding': 'cdr', 'schemaName': 'std_msgs/msg/String'}]
        await ws.send(json.dumps({'op': 'advertise', 'channels': channels}))
        await asyncio.sleep(2.0)
        for _ in range(20):                                    # 10 s of messages, one per 0.5 s per topic
            for cid, text in ((1, 'to /allowed'), (2, 'to /not_allowed')):
                await ws.send(b'\x01' + struct.pack('<I', cid) + cdr_string(text))
            await asyncio.sleep(0.5)
        try:                                                  # any status the bridge sent (e.g. a refusal)
            while True:
                m = await asyncio.wait_for(ws.recv(), 0.5)
                if isinstance(m, str) and '"status"' in m:
                    print('status', m, flush=True)
        except (asyncio.TimeoutError, websockets.ConnectionClosed):
            pass


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else 'ws://127.0.0.1:8765'))
