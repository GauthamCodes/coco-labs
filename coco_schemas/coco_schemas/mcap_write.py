# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
A small writer for UNCOMPRESSED coco run files (MCAP; M3.1).

The counterpart of :mod:`coco_schemas.mcap_read`, for Python producers that
have protobuf but no zstd -- the ROS-to-event adapter in ``coco_lab_ros``.
It writes what ``lab_web/src/schemas/mcap.ts`` writes, minus compression and
the summary section: the magic, a header (profile ``coco``), one protobuf
schema per message type (its ``FileDescriptorSet``: the message's file and
every file it depends on, as the TypeScript writer registers them), one
channel per topic, the messages in the order given, a ``coco`` metadata
record (``run_id``), DataEnd, a footer with no summary, and the magic.

The site's Case Files are this file re-chunked with zstd by
``lab_web/tools/build_casefiles.mjs`` -- the same messages, byte for byte.
"""

import json
import struct
from typing import Dict, List, Tuple

from google.protobuf import descriptor_pb2

MAGIC = b'\x89MCAP0\r\n'
OP_HEADER, OP_FOOTER, OP_SCHEMA, OP_CHANNEL, OP_MESSAGE = 0x01, 0x02, 0x03, 0x04, 0x05
OP_METADATA, OP_DATA_END = 0x0C, 0x0F
PROFILE = 'coco'
LIBRARY = 'coco_schemas.mcap_write 1'


def _str(s: str) -> bytes:
    b = s.encode('utf-8')
    return struct.pack('<I', len(b)) + b


def _map(m: Dict[str, str]) -> bytes:
    body = b''.join(_str(k) + _str(v) for k, v in sorted(m.items()))
    return struct.pack('<I', len(body)) + body


def _record(op: int, body: bytes) -> bytes:
    return struct.pack('<BQ', op, len(body)) + body


def file_descriptor_set(descriptor) -> bytes:
    """Return a message type's FileDescriptorSet: its file and every dependency, deps first."""
    out: List[descriptor_pb2.FileDescriptorProto] = []
    seen = set()

    def visit(fd):
        if fd.name in seen:
            return
        seen.add(fd.name)
        for dep in fd.dependencies:
            visit(dep)
        p = descriptor_pb2.FileDescriptorProto()
        fd.CopyToProto(p)
        out.append(p)
    visit(descriptor.file)
    return descriptor_pb2.FileDescriptorSet(file=out).SerializeToString()


class RunWriter:
    """Collect messages, then :meth:`finish` returns the file's bytes."""

    def __init__(self) -> None:
        """Start an empty run."""
        self._schemas: Dict[str, int] = {}
        self._channels: Dict[str, Tuple[int, int]] = {}
        self._defs: List[bytes] = []
        self._messages: List[bytes] = []
        self.count = 0

    def _schema(self, msg) -> int:
        name = msg.DESCRIPTOR.full_name
        sid = self._schemas.get(name)
        if sid is None:
            sid = self._schemas[name] = len(self._schemas) + 1
            fds = file_descriptor_set(msg.DESCRIPTOR)
            body = (struct.pack('<H', sid) + _str(name) + _str('protobuf')
                    + struct.pack('<I', len(fds)) + fds)
            self._defs.append(_record(OP_SCHEMA, body))
        return sid

    def add(self, channel: str, msg, log_time_ns: int, sequence: int = 0) -> None:
        """Append one protobuf message on ``channel`` at ``log_time_ns`` (kept in order)."""
        sid = self._schema(msg)
        ch = self._channels.get(channel)
        if ch is None:
            cid = len(self._channels)
            ch = self._channels[channel] = (cid, sid)
            body = struct.pack('<HH', cid, sid) + _str(channel) + _str('protobuf') + _map({})
            self._defs.append(_record(OP_CHANNEL, body))
        elif ch[1] != sid:
            raise ValueError(f'channel {channel!r} already carries another message type')
        if log_time_ns < 0:
            raise ValueError('log time must not be negative')
        data = msg.SerializeToString()
        body = struct.pack('<HIQQ', ch[0], sequence & 0xFFFFFFFF, log_time_ns,
                           log_time_ns) + data
        # a schema/channel record must precede its first message: flush definitions first
        self._messages.extend(self._defs)
        self._defs = []
        self._messages.append(_record(OP_MESSAGE, body))
        self.count += 1

    def finish(self, run_id: str = '') -> bytes:
        """Return the whole file."""
        header = _record(OP_HEADER, _str(PROFILE) + _str(LIBRARY))
        meta = _record(OP_METADATA, _str('coco') + _map({'run_id': run_id}))
        data_end = _record(OP_DATA_END, struct.pack('<I', 0))
        footer = _record(OP_FOOTER, struct.pack('<QQI', 0, 0, 0))
        return (MAGIC + header + b''.join(self._messages) + b''.join(self._defs) + meta
                + data_end + footer + MAGIC)


def write_json_scalar(obj) -> bytes:
    """Canonical JSON bytes (sorted keys, no spaces): a run spec's bytes."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')
