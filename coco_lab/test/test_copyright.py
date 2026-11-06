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

from ament_copyright.main import main
import pytest


@pytest.mark.copyright
@pytest.mark.linter
def test_copyright():
    # R2: coco_lab/templates holds user algorithm files, under their authors' licences
    templates = [str(p) for p in sorted(Path(__file__).resolve().parents[1].glob(
        'coco_lab/templates/*.py'))]
    rc = main(argv=['--exclude', *templates, *[os.path.relpath(t) for t in templates], '--',
                    '.', 'test'])
    assert rc == 0, 'Found errors'
