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
Say in the report header which coco_lab, and which oracle, was tested.

A pip-installed run and a colcon run must not be confused with a run of the
source tree, and the pins in requirements-test.txt are only evidence if
the run shows the versions it actually used.
"""


def pytest_report_header(config):
    import coco_lab
    import hypothesis
    import networkx
    return [f'coco_lab {coco_lab.__version__} from {coco_lab.__file__}',
            f'hypothesis {hypothesis.__version__}, '
            f'networkx {networkx.__version__}']
