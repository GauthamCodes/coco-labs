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
A small reader for UNCOMPRESSED coco run files (MCAP; M2.7).

Enough of the MCAP format (https://mcap.dev/spec) to read what
``lab_web/src/schemas/mcap.ts`` writes without compression: the magic, the
records, chunks whose compression is the empty string, schemas, channels
and messages. A compressed chunk is refused, never guessed at -- Python
here has no zstd. Messages come back in FILE order, with their channel's
topic, the schema name, the log time and the sequence.
"""

import struct
from typing import Dict, Iterator, List, NamedTuple, Tuple

MAGIC = b'\x89MCAP0\r\n'
OP_SCHEMA, OP_CHANNEL, OP_MESSAGE, OP_CHUNK = 0x03, 0x04, 0x05, 0x06


class McapError(ValueError):
    """A file this reader will not read."""


class Message(NamedTuple):
    """One message: where it was logged, what it is, its bytes."""

    channel: str
    schema: str
    log_time: int
    sequence: int
    data: bytes


def _str(b: bytes, o: int) -> Tuple[str, int]:
    (n,) = struct.unpack_from('<I', b, o)
    return b[o + 4:o + 4 + n].decode('utf-8'), o + 4 + n


def _records(b: bytes, o: int, end: int) -> Iterator[Tuple[int, bytes]]:
    while o < end:
        op = b[o]
        (n,) = struct.unpack_from('<Q', b, o + 1)
        yield op, b[o + 9:o + 9 + n]
        o += 9 + n


def read_messages(data: bytes) -> List[Message]:
    """Return every message of an uncompressed run file, in file order."""
    if data[:8] != MAGIC or data[-8:] != MAGIC:
        raise McapError('not an MCAP file')
    schemas: Dict[int, str] = {}
    channels: Dict[int, Tuple[str, int]] = {}
    out: List[Message] = []

    def take(op: int, body: bytes) -> None:
        if op == OP_SCHEMA:
            (sid,) = struct.unpack_from('<H', body, 0)
            name, _ = _str(body, 2)
            schemas[sid] = name
        elif op == OP_CHANNEL:
            cid, sid = struct.unpack_from('<HH', body, 0)
            topic, _ = _str(body, 4)
            channels[cid] = (topic, sid)
        elif op == OP_MESSAGE:
            cid, seq, log_time, _pub = struct.unpack_from('<HIQQ', body, 0)
            topic, sid = channels[cid]
            out.append(Message(topic, schemas[sid], log_time, seq,
                               bytes(body[22:])))
        elif op == OP_CHUNK:
            o = 8 + 8 + 8 + 4
            comp, o = _str(body, o)
            if comp:
                raise McapError(f'a {comp!r} chunk: this reader reads '
                                'uncompressed files only')
            (n,) = struct.unpack_from('<Q', body, o)
            o += 8
            for op2, body2 in _records(body, o, o + n):
                take(op2, body2)

    for op, body in _records(data, 8, len(data) - 8):
        take(op, body)
    return out
