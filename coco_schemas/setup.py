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

package_name = 'coco_schemas'
# realpath: colcon --symlink-install runs this file through a symlink.
here = os.path.dirname(os.path.realpath(__file__))


def _proto_files():
    """Install the .proto sources next to the package's share files."""
    out = {}
    root = os.path.join(here, 'proto')
    for d, _, names in os.walk(root):
        rel = os.path.relpath(d, here)
        files = [os.path.join(rel, n) for n in names if n.endswith('.proto')]
        if files:
            out[os.path.join('share', package_name, rel)] = files
    return list(out.items())


setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/compat', ['compat/v1.binpb']),
    ] + _proto_files(),
    install_requires=['protobuf'],
    python_requires='>=3.10',
    zip_safe=True,
    maintainer='gautham',
    maintainer_email='gauthamanil888@gmail.com',
    description='COCO Lab v2 event schemas (protobuf), no ROS',
    license='Apache-2.0',
)
