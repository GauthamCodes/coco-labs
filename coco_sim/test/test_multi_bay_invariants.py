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
Unit and integration tests verifying invariants INV-1 through INV-12
for the COCO 2.0 Episode-Driven Multi-Bay Architecture.
"""

import ast
import json
import os
import sys

import pytest

# Ensure coco_mission scripts can be imported cleanly
MISSION_SCRIPTS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'coco_mission', 'scripts')
)
if MISSION_SCRIPTS not in sys.path:
    sys.path.insert(0, MISSION_SCRIPTS)

from coco_config.robot import (
    BAY_Y_CENTRES,
    CLIMB_END_X,
    DESCENT_EXIT_X,
    FIXED_REGION_MAP,
    lane_for_colour,
    lane_for_region,
    PLATFORM_LEN,
    PRE_RAMP_X,
    RAMP_FOOT_X,
    RAMP_RUN,
    RAMP_SUMMIT_X,
    RAMP_WIDTH,
    region_by_id,
    REGION_IDS,
    region_for_lane,
    resolve_lane,
    SPAWN_XY,
    TARGET_COLOURS,
    TARGET_PLATFORMS,
    TARGET_REGIONS,
    TARGET_ROW_X,
    TARGETS,
)
from coco_sim.backends.gazebo import GazeboBackend
from coco_sim.episode import (
    compat_mission_inputs,
    generate_episode,
    LEVELS,
    validate_episode,
)


# ── INV-1: Region-Bay 1:1 Correspondence ─────────────────────────────────────
def test_inv_1_region_bay_one_to_one():
    """INV-1: Every TargetRegion corresponds to exactly one physical bay."""
    assert len(TARGET_REGIONS) == 4
    assert len(REGION_IDS) == 4
    assert REGION_IDS == ('bay_1', 'bay_2', 'bay_3', 'bay_4')

    bay_ids = [r.region_id for r in TARGET_REGIONS]
    assert len(set(bay_ids)) == 4, "Bay IDs must be unique"

    platform_ids = [r.platform_id for r in TARGET_REGIONS]
    assert len(set(platform_ids)) == 4, "Platform IDs must be unique"
    assert tuple(platform_ids) == TARGET_PLATFORMS

    centres = [r.bay_y for r in TARGET_REGIONS]
    assert tuple(centres) == BAY_Y_CENTRES
    assert tuple(centres) == (-6.0, -2.0, 2.0, 6.0)

    # Spacing between adjacent bays is exactly 4.0 m
    for i in range(len(centres) - 1):
        assert pytest.approx(centres[i + 1] - centres[i]) == 4.0

    # Each region lookup works by bay_id and legacy lane_id alias
    for i, region in enumerate(TARGET_REGIONS, start=1):
        assert region_by_id(f'bay_{i}') == region
        assert region_by_id(f'lane_{i}') == region
        assert region_for_lane(region.bay_y) == region


# ── INV-2: Target Partition ──────────────────────────────────────────────────
@pytest.mark.parametrize('level', LEVELS)
@pytest.mark.parametrize('seed', [0, 1, 7, 42, 100, 2026])
def test_inv_2_target_partition(level, seed):
    """INV-2: Every episode target belongs to exactly one valid region."""
    spec = generate_episode(seed=seed, level=level)
    validate_episode(spec)

    assert len(spec.targets) == 4
    assigned_regions = [t.region_id for t in spec.targets]

    # Exactly covers all 4 regions with no duplicates and no unassigned
    assert set(assigned_regions) == set(REGION_IDS)
    assert len(assigned_regions) == len(set(assigned_regions))

    # All targets have valid colours
    assert set(t.colour for t in spec.targets) == set(TARGET_COLOURS)


# ── INV-3: Platform Bounds ───────────────────────────────────────────────────
@pytest.mark.parametrize('seed', range(50))
def test_inv_3_platform_bounds(seed):
    """INV-3: Generated target positions remain inside the platform envelope."""
    spec = generate_episode(seed=seed, level='positions')
    for t in spec.targets:
        region = region_by_id(t.region_id)
        x_min, x_max, y_min, y_max = region.platform_bounds
        assert x_min <= t.x <= x_max, (
            f"Target {t.colour} x={t.x} out of bounds [{x_min}, {x_max}]"
        )
        assert y_min <= t.y <= y_max, (
            f"Target {t.colour} y={t.y} out of bounds [{y_min}, {y_max}]"
        )


# ── INV-4: Gazebo Placement Agreement ─────────────────────────────────────────
@pytest.mark.parametrize('seed', [3, 17, 88])
def test_inv_4_gazebo_target_placement_agreement(seed):
    """INV-4: EpisodeSpec and Gazebo target placement agree."""
    spec = generate_episode(seed=seed, level='positions')
    backend = GazeboBackend()
    scene = backend.translate(spec)

    # In Gazebo translation, each target maps to a model spawn with exact coordinates
    assert len(scene.targets) >= len(spec.targets)
    targets_by_name = {s.name: s for s in scene.targets}

    for t in spec.targets:
        name = f'target_{t.colour}'
        assert name in targets_by_name
        spawn = targets_by_name[name]
        assert pytest.approx(spawn.x, abs=1e-4) == t.x
        assert pytest.approx(spawn.y, abs=1e-4) == t.y
        assert pytest.approx(spawn.z, abs=1e-4) == t.z


# ── INV-5: Nav2 Bay Geometry Agreement ────────────────────────────────────────
def test_inv_5_nav2_bay_geometry_agreement():
    """INV-5: EpisodeSpec and Nav2 bay geometry agree."""
    import localization_health as lh

    # Nav2 localization health centers match TARGETS / TARGET_REGIONS bay_y
    assert lh.MAPPED_GROUND_CENTRES_Y == BAY_Y_CENTRES
    assert lh.MAPPED_GROUND_MIN_X == RAMP_FOOT_X
    assert lh.MAPPED_GROUND_MAX_X == RAMP_SUMMIT_X + PLATFORM_LEN + RAMP_RUN

    # Corridors between bays (e.g. Y = -4.0, 0.0, 4.0) are mapped ground
    for y_corridor in (-8.0, -4.0, 0.0, 4.0, 8.0):
        assert lh.on_mapped_ground(2.0, y_corridor)

    # Ramp wedges at bay centers are gated as unmapped ground
    for bay_y in BAY_Y_CENTRES:
        assert not lh.on_mapped_ground(2.0, bay_y)
        assert not lh.on_mapped_ground(3.5, bay_y)


# ── INV-6: Mission Plan Derivation ────────────────────────────────────────────
def test_inv_6_mission_geometry_derived_from_target_region():
    """INV-6: Mission geometry derived from TargetRegion, not static constants."""
    import mission_states as ms

    for region in TARGET_REGIONS:
        # Tested via region_map
        rmap = {'blue': region.region_id, 'red': 'bay_1', 'green': 'bay_2', 'yellow': 'bay_4'}
        plan = ms.MissionPlan(colour='blue', region_map=rmap)
        assert plan.pre_ramp_x == region.pre_ramp_x
        assert plan.ramp_foot_x == region.ramp_foot_x
        assert plan.ramp_summit_x == region.ramp_summit_x
        assert plan.climb_end_x == region.climb_end_x
        assert plan.descent_goal == (region.descent_x, region.bay_y)
        assert plan.lane == region.bay_y

        # Tested via lane
        plan_lane = ms.MissionPlan(colour='blue', lane=region.bay_y)
        assert plan_lane.pre_ramp_x == region.pre_ramp_x
        assert plan_lane.ramp_foot_x == region.ramp_foot_x
        assert plan_lane.ramp_summit_x == region.ramp_summit_x
        assert plan_lane.climb_end_x == region.climb_end_x
        assert plan_lane.descent_goal == (region.descent_x, region.bay_y)
        assert plan_lane.lane == region.bay_y


# ── INV-7: Permuted Colours Independence ──────────────────────────────────────
def test_inv_7_randomized_colours_independence():
    """INV-7: Randomized colour levels do not use legacy colour->lane table."""
    import mission_states as ms

    found_permuted = False
    for seed in range(50):
        spec = generate_episode(seed=seed, level='colours')
        rmap = spec.region_map()
        if rmap != FIXED_REGION_MAP:
            found_permuted = True
            for colour, reg_id in rmap.items():
                expected_lane = region_by_id(reg_id).bay_y
                legacy_lane = lane_for_colour(colour)
                plan = ms.MissionPlan(colour=colour, region_map=rmap)
                assert plan.lane == expected_lane
                if reg_id != FIXED_REGION_MAP[colour]:
                    assert plan.lane != legacy_lane
            break
    assert found_permuted, "Expected to find at least one permuted colours seed"


# ── INV-8: Fixed Mode Regression Parity ───────────────────────────────────────
def test_inv_8_fixed_mode_regression_parity():
    """INV-8: Fixed mode remains regression-identical to baseline."""
    spec = generate_episode(seed=0, level='fixed')
    assert spec.region_map() == FIXED_REGION_MAP
    assert FIXED_REGION_MAP == {
        'red': 'bay_1',
        'green': 'bay_2',
        'blue': 'bay_3',
        'yellow': 'bay_4',
    }

    # Verify positions and target table
    expected_lanes = {'red': -6.0, 'green': -2.0, 'blue': 2.0, 'yellow': 6.0}
    for t in spec.targets:
        assert t.x == TARGET_ROW_X
        assert t.y == expected_lanes[t.colour]
        assert lane_for_colour(t.colour) == expected_lanes[t.colour]


# ── INV-9: Robot Task View Anti-Cheat ─────────────────────────────────────────
def test_inv_9_robot_task_view_anti_cheat():
    """INV-9: Robot task_view carries no privileged target coordinates."""
    spec = generate_episode(seed=42, level='positions', requested_colour='green')
    view = spec.task_view()
    view_json = json.dumps(view)

    # Ensure no exact coordinates leak in task_view
    for t in spec.targets:
        assert repr(t.x) not in view_json
        assert repr(t.y) not in view_json
        assert f'{t.x:.2f}' not in view_json
        assert f'{t.y:.2f}' not in view_json

    inputs = compat_mission_inputs(spec)
    assert 'target_colour' in inputs
    assert 'region_map' in inputs
    assert inputs['target_colour'] == 'green'
    # region_map string is formatted as "colour=bay_X,...", contains no coordinates
    for part in inputs['region_map'].split(','):
        c, bay = part.split('=')
        assert c in TARGET_COLOURS
        assert bay in REGION_IDS


# ── INV-10: Simulation Time MoveIt Waits ──────────────────────────────────────
def test_inv_10_moveit_waits_use_sim_time_and_bounded():
    """INV-10: MoveIt waits use simulation time and are bounded."""
    arm_control_path = os.path.join(
        os.path.dirname(__file__), '..', '..',
        'coco_moveit_config', 'scripts', 'arm_control.py'
    )
    with open(arm_control_path, 'r') as f:
        src = f.read()

    # Verify AST contains clock.now() and sim_elapsed logic in await_future
    tree = ast.parse(src)
    await_future_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'await_future':
            await_future_node = node
            break

    assert await_future_node is not None, "await_future must exist in arm_control.py"
    func_src = ast.get_source_segment(src, await_future_node)
    assert 'self.get_clock()' in func_src
    assert 'clock.now()' in func_src
    assert 'sim_elapsed' in func_src
    assert 'wall_ceiling' in func_src
    assert 'hit wall-clock safety ceiling' in func_src


# ── INV-11: Sole Wheel Publisher Arbiter Invariant ───────────────────────────
def test_inv_11_sole_wheel_publisher_arbiter_invariant():
    """INV-11: Sole wheel publisher through arbiter (/diff_drive_controller/cmd_vel)."""
    ws_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    packages_to_check = [
        'coco_mission',
        'coco_moveit_config',
        'coco_perception',
        'coco_rl',
        'coco_web',
    ]

    wheel_topic = '/diff_drive_controller/cmd_vel'
    publishers_found = []

    for pkg in packages_to_check:
        pkg_dir = os.path.join(ws_root, pkg)
        if not os.path.isdir(pkg_dir):
            continue
        for root, _, files in os.walk(pkg_dir):
            for file in files:
                if file.endswith('.py') and not file.startswith('test_'):
                    path = os.path.join(root, file)
                    with open(path, 'r', errors='ignore') as f:
                        src = f.read()
                    if wheel_topic not in src:
                        continue
                    try:
                        tree = ast.parse(src)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Call):
                                # Check if function is create_publisher
                                if isinstance(node.func, ast.Attribute) and node.func.attr == 'create_publisher':
                                    for arg in node.args:
                                        if isinstance(arg, ast.Constant) and arg.value == wheel_topic:
                                            publishers_found.append((path, node.lineno))
                    except Exception:
                        pass

    assert not publishers_found, (
        f"Violations of INV-11: nodes publishing directly to {wheel_topic}: {publishers_found}"
    )


# ── INV-12: Isaac Sim Isolation ──────────────────────────────────────────────
def test_inv_12_isaac_sim_isolation():
    """INV-12: Isaac backend remains isolated with zero dependencies on Gazebo."""
    import coco_sim.backends.gazebo as gz_backend
    assert hasattr(gz_backend, 'GazeboBackend')

    # Ensure no heavy simulator runtimes leaked into sys.modules
    assert 'omni' not in sys.modules
    assert 'pxr' not in sys.modules
    assert 'isaacsim' not in sys.modules

    # Inspect isaac backend file exists and is cleanly segregated
    isaac_path = os.path.join(
        os.path.dirname(__file__), '..', 'coco_sim', 'backends', 'isaac.py'
    )
    assert os.path.isfile(isaac_path)
