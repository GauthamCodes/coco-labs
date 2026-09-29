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

import os

from setuptools import find_packages, setup

package_name = 'coco_lab'
# realpath, not abspath: `colcon build --symlink-install` (which
# scripts/build_overlay.sh requires) runs this file through a symlink in the
# build directory, where requirements-test.txt does not exist.
here = os.path.dirname(os.path.realpath(__file__))


def _test_requirements():
    """Read the pinned test-only dependencies, one source of truth."""
    with open(os.path.join(here, 'requirements-test.txt')) as f:
        return [line.strip() for line in f
                if line.strip() and not line.startswith('#')]


setup(
    name=package_name,
    version='0.2.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    # Standard library only. test_stdlib_only.py enforces it.
    install_requires=[],
    python_requires='>=3.10',
    zip_safe=True,
    maintainer='gautham',
    maintainer_email='gauthamanil888@gmail.com',
    description='COCO Lab core: traced graph search, no ROS',
    license='Apache-2.0',
    extras_require={
        'test': _test_requirements(),
    },
)
