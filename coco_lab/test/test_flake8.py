# Copyright 2017 Open Source Robotics Foundation, Inc.
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

from ament_flake8.main import main_with_errors
import pytest


@pytest.mark.flake8
@pytest.mark.linter
def test_flake8():
    # The vendored ISRO code keeps its original style (coco_lab/isro). R2: coco_lab/templates
    # holds algorithm FILES (coco_lab.api's starters: user code, data to this package, never
    # imported); parity CI and the ROS 2 runs name their exact bytes by sha256, so they are not
    # restyled.
    rc, errors = main_with_errors(argv=['--exclude', 'upstream_v3_6.py,templates'])
    assert rc == 0, \
        'Found %d code style errors / warnings:\n' % len(errors) + \
        '\n'.join(errors)
