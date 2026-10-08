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
COCO Lab v2's event schemas (README section 5.2; docs/v2/SCHEMAS.md).

- ``coco_schemas.channels``: every channel's name and message.
- ``coco_schemas.runid``: the run identity hash.
- ``coco_schemas.trace_v1``: v1 coco_lab traces <-> v2 messages, losslessly.
- ``coco_schemas.compat``: the within-major compatibility rules CI enforces.
- ``coco_schemas.gen``: protoc's generated Python (do not edit; regenerate
  with ``coco_schemas/scripts/generate.py``).

No rclpy anywhere; ``coco_lab`` does not import this package (ADR 0001:
the browser engine stays dependency-free and emits columns).
"""

__version__ = '1.0.0'
