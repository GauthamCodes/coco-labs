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
lab_stack.launch.py resolves to exactly the plan's bringup (plan §C.3).

The arbiter with ``initial_mode:=nav`` (its mode set through the existing
launch parameter -- nothing publishes /mission/mode), nav.launch.py with
``arbiter:=true`` and the MERGED parameters, and the lab node only when
asked. Nothing else: no executive, perception, MoveIt, web or RViz.
"""

import importlib.util
import os

from coco_lab_ros import params
from launch import LaunchContext
from launch.actions import IncludeLaunchDescription
from launch.utilities import (normalize_to_list_of_substitutions,
                              perform_substitutions)
from launch_ros.actions import Node

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
LAUNCH = os.path.join(PKG, 'launch', 'lab_stack.launch.py')


def load():
    spec = importlib.util.spec_from_file_location('lab_stack', LAUNCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def resolve(**args):
    mod = load()
    ld = mod.generate_launch_description()
    ctx = LaunchContext()
    for a in ld.entities:
        if hasattr(a, 'default_value') and hasattr(a, 'name'):
            value = args.get(a.name)
            if value is None:
                value = ''.join(s.perform(ctx) for s in a.default_value)
            ctx.launch_configurations[a.name] = value
    return mod.stack(ctx), ctx


def test_the_stack_is_arbiter_nav_and_nothing_else(tmp_path):
    merged = tmp_path / 'm.yaml'
    repo = os.path.dirname(PKG)
    params.merge_files(
        os.path.join(repo, 'gazebo_models', 'config', 'nav2_params.yaml'),
        os.path.join(PKG, 'config', 'nav2_lab_overlay.yaml'), str(merged))
    entities, ctx = resolve(params_file=str(merged))
    includes = [e for e in entities if isinstance(e, IncludeLaunchDescription)]
    nodes = [e for e in entities if isinstance(e, Node)]
    assert len(includes) == 2 and len(nodes) == 1
    for i in includes:              # resolves (and loads) the source
        i.launch_description_source.get_launch_description(ctx)
    files = [os.path.basename(i.launch_description_source.location)
             for i in includes]
    assert files == ['arbiter.launch.py', 'nav.launch.py']

    def text(x):
        return perform_substitutions(
            ctx, normalize_to_list_of_substitutions(x))

    def args(inc):
        return {text(k): text(v) for k, v in inc.launch_arguments}
    assert args(includes[0])['initial_mode'] == 'nav'
    nav = args(includes[1])
    assert nav['arbiter'] == 'true' and nav['params_file'] == str(merged)
    assert nodes[0].node_executable == 'lab_planner'


def test_without_params_file_it_merges_the_overlay_itself():
    mod = load()
    ctx = LaunchContext()
    ctx.launch_configurations['params_file'] = ''
    try:
        path = mod.merged_params(ctx)
    except Exception as exc:        # outside an installed overlay
        raise AssertionError(f'could not merge: {exc}')
    doc = params.load(path)
    assert doc['planner_server']['ros__parameters']['planner_plugins'] == \
        ['GridBased', 'NavFn', 'NavFnAStar']
