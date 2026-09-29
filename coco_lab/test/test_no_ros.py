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
coco_lab must never import rclpy (CLAUDE.md, COCO Lab platform rule 1).

The same code runs in CI, in the browser under Pyodide and inside a ROS
node; only the first two make that promise checkable, and only if ROS never
leaks in. This is the mujoco_env pattern (coco_rl/test/
test_mujoco_env_has_no_ros.py): rather than grepping for the word, it
evicts every ROS module and coco_lab from ``sys.modules`` and poisons the
import machinery, so ANY transitive ROS import fails loudly.
"""

import builtins
import importlib
import pkgutil
import sys

import pytest

BANNED = ('rclpy', 'rosidl_runtime_py', 'rmw', 'ament_index_python',
          'rosidl_parser', 'rcl_interfaces', 'builtin_interfaces')


@pytest.fixture
def no_ros(monkeypatch):
    """Make importing anything ROS raise, then hand control back."""
    for name in list(sys.modules):
        if name.split('.')[0] in BANNED or name.split('.')[0] == 'coco_lab':
            monkeypatch.delitem(sys.modules, name, raising=False)

    real_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split('.')[0] in BANNED:
            raise AssertionError(
                f'coco_lab pulled in {name!r}. coco_lab never imports ROS '
                f'-- see CLAUDE.md "COCO Lab direction", rule 1.')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', guarded)
    yield


def all_modules():
    """Every module in coco_lab, subpackages included (coco_lab.isro)."""
    import coco_lab
    return ['coco_lab'] + [
        m.name for m in pkgutil.walk_packages(coco_lab.__path__,
                                              prefix='coco_lab.')]


def test_the_walk_reaches_subpackages():
    assert 'coco_lab.isro.upstream_v3_6' in all_modules()


def test_every_module_imports_without_ros(no_ros):
    names = all_modules()
    assert len(names) >= 6, names
    for name in names:
        importlib.import_module(name)


def test_the_guard_itself_works(no_ros):
    """A guard that cannot fail proves nothing."""
    with pytest.raises(AssertionError):
        import rclpy  # noqa: F401


def test_no_ros_module_is_in_sys_modules_after_import(no_ros):
    for name in all_modules():
        importlib.import_module(name)
    leaked = [n for n in sys.modules if n.split('.')[0] in BANNED]
    assert not leaked, f'ROS modules present after import: {leaked}'
