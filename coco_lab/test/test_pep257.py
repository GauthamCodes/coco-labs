# Copyright 2015 Open Source Robotics Foundation, Inc.
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

import os
from pathlib import Path

from ament_pep257.main import main
import pytest


@pytest.mark.linter
@pytest.mark.pep257
def test_pep257():
    # The vendored ISRO code keeps its original style (coco_lab/isro).
    # R2: coco_lab/templates holds user algorithm files (see test_flake8.py)
    templates = [str(p) for p in sorted(Path(__file__).resolve().parents[1].glob(
        'coco_lab/templates/*.py'))]
    rc = main(argv=['--exclude', 'coco_lab/isro/upstream_v3_6.py', *templates,
                    *[os.path.relpath(t) for t in templates], '--', '.', 'test'])
    assert rc == 0, 'Found code style errors / warnings'
