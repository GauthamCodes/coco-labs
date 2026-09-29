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
The ISRO simulator's historical search, kept apart from coco_lab's own.

- :mod:`coco_lab.isro.upstream_v3_6` -- the historical functions, verbatim
  and hash-checked. Historical behaviour, not a reference: it is what the
  simulator did, including its cell-only state (see
  ``docs/labs/ISRO_INVESTIGATION.md``).
- :mod:`coco_lab.isro.historical` -- the harness that runs them on a
  :class:`coco_lab.maps.LabMap`.

The corrected model is :class:`coco_lab.heading.HeadingGrid`, searched by
the ordinary :mod:`coco_lab.search` algorithms.
"""
