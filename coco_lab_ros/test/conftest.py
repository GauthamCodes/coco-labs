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

"""Put the test directory on sys.path, and say what was tested."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def pytest_collection_modifyitems(config, items):
    """
    Run the ament linters first, before any rclpy thread exists.

    ament_flake8 checks files in a forked multiprocessing pool. Forked
    after this suite's rclpy executors have run threads in the process, a
    worker can inherit a held lock and block forever on a futex -- measured
    at 1C-2: the whole suite hung for 10 minutes with every flake8 worker
    in futex_wait. A stable sort moves the linters to the front and keeps
    every other test's order.
    """
    items.sort(key=lambda item: 0 if item.get_closest_marker('linter')
               else 1)


def pytest_report_header(config):
    import coco_lab
    import coco_lab_ros
    return [f'coco_lab {coco_lab.__version__} from {coco_lab.__file__}',
            f'coco_lab_ros {coco_lab_ros.__version__} from '
            f'{coco_lab_ros.__file__}']
