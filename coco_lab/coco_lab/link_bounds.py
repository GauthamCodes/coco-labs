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

"""Reference-side limits, read from the same file as browser and coco verify."""
import json
from pathlib import Path

LIMITS = json.loads(Path(__file__).with_name('link_limits.json').read_text())


def validate_log(inputs, error=ValueError):
    """Reject pathological tick logs before constructing an Arena."""
    if not isinstance(inputs, list) or len(inputs) > LIMITS['inputs']:
        raise error(f"Link permits at most {LIMITS['inputs']} inputs")
    prev = -1
    for i, r in enumerate(inputs):
        t = r.get('tick') if isinstance(r, dict) else None
        bound = LIMITS['first_tick'] if i == 0 else LIMITS['ticks']
        if (not isinstance(t, int) or isinstance(t, bool) or
                not 0 <= t <= bound or t < prev):
            raise error(f'Link tick must be ordered and between 0 and {bound}')
        prev = t
