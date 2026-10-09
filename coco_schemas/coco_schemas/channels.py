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
Every channel: its name, its family, and the message it carries.

Names are ``coco.<family>.<name>.v<major>`` (README section 5.2). The
major in the name equals the major of the message's protobuf package
(``coco.plan.v1`` for ``...v1``), and a test holds the two together.
``stream`` channels carry ``*Batch`` messages whose fields 1-3 are the
three clocks every event carries: ``seq``, ``tick``, ``t_world``.
"""

import re
from typing import NamedTuple

NAME = re.compile(r'^coco\.(?P<body>[a-z_]+(?:\.[a-z_]+)+)\.v(?P<major>\d+)$')


class Channel(NamedTuple):
    """One channel."""

    name: str
    family: str
    message: str      # fully qualified protobuf message name
    stream: bool      # True: per-event batches; False: one record (static)


CHANNELS = (
    Channel('coco.envelope.manifest.v1', 'envelope',
            'coco.envelope.v1.Manifest', False),
    Channel('coco.world.grid.v1', 'world', 'coco.world.v1.WorldGrid', False),
    Channel('coco.world.geometry.v1', 'world',
            'coco.world.v1.WorldGeometry', False),
    Channel('coco.robot.params.v1', 'robot', 'coco.robot.v1.RobotParams',
            False),
    Channel('coco.robot.state.v1', 'robot', 'coco.robot.v1.RobotStateBatch',
            True),
    Channel('coco.truth.pose.v1', 'truth', 'coco.truth.v1.TruthPoseBatch',
            True),
    Channel('coco.sensor.scan.lidar.v1', 'sensor.scan',
            'coco.sensor.v1.ScanBatch', True),
    Channel('coco.plan.search.header.v1', 'plan.search',
            'coco.plan.v1.SearchHeader', False),
    Channel('coco.plan.search.events.v1', 'plan.search',
            'coco.plan.v1.SearchEventBatch', True),
    Channel('coco.plan.search.summary.v1', 'plan.search',
            'coco.plan.v1.SearchSummary', False),
    Channel('coco.plan.incremental.header.v1', 'plan.incremental',
            'coco.plan.v1.IncrementalHeader', False),
    Channel('coco.plan.incremental.events.v1', 'plan.incremental',
            'coco.plan.v1.IncrementalEventBatch', True),
    Channel('coco.plan.path.poses.v1', 'plan.path', 'coco.plan.v1.PathBatch',
            True),
    Channel('coco.input.events.v1', 'input', 'coco.input.v1.InputEventBatch',
            True),
    Channel('coco.metrics.values.v1', 'metrics',
            'coco.metrics.v1.MetricBatch', True),
    Channel('coco.annotation.text.v1', 'annotation',
            'coco.annotation.v1.AnnotationBatch', True),
    # -- M2.1: the whole loop's families (additive within v1) -------------
    Channel('coco.estimate.pose.v1', 'estimate',
            'coco.estimate.v1.EstimateBatch', True),
    Channel('coco.localise.particles.header.v1', 'localise.particles',
            'coco.localise.v1.FilterHeader', False),
    Channel('coco.localise.particles.set.v1', 'localise.particles',
            'coco.localise.v1.ParticleSetBatch', True),
    Channel('coco.localise.particles.update.v1', 'localise.particles',
            'coco.localise.v1.ParticleUpdateBatch', True),
    Channel('coco.localise.ekf.header.v1', 'localise.ekf',
            'coco.localise.v1.FilterHeader', False),
    Channel('coco.localise.ekf.update.v1', 'localise.ekf',
            'coco.localise.v1.EkfUpdateBatch', True),
    Channel('coco.map.grid.header.v1', 'map.grid',
            'coco.map.v1.MapGridHeader', False),
    Channel('coco.map.grid.snapshot.v1', 'map.grid',
            'coco.map.v1.MapGridSnapshotBatch', True),
    Channel('coco.map.grid.cells.v1', 'map.grid',
            'coco.map.v1.MapCellBatch', True),
    Channel('coco.map.slam.header.v1', 'map.slam',
            'coco.map.v1.SlamHeader', False),
    Channel('coco.map.slam.landmarks.v1', 'map.slam',
            'coco.map.v1.LandmarkBatch', True),
    Channel('coco.map.slam.particles.v1', 'map.slam',
            'coco.map.v1.SlamParticleBatch', True),
    Channel('coco.map.slam.nodes.v1', 'map.slam',
            'coco.map.v1.GraphNodeBatch', True),
    Channel('coco.map.slam.edges.v1', 'map.slam',
            'coco.map.v1.GraphEdgeBatch', True),
    Channel('coco.control.local.header.v1', 'control.local',
            'coco.control.v1.ControllerHeader', False),
    Channel('coco.control.local.candidates.v1', 'control.local',
            'coco.control.v1.CandidateBatch', True),
    Channel('coco.control.local.command.v1', 'control.local',
            'coco.control.v1.CommandBatch', True),
    Channel('coco.decide.search.header.v1', 'decide.search',
            'coco.decide.v1.SearchProblemHeader', False),
    Channel('coco.decide.search.belief.v1', 'decide.search',
            'coco.decide.v1.BeliefBatch', True),
    Channel('coco.decide.search.orders.v1', 'decide.search',
            'coco.decide.v1.OrderCostBatch', True),
    Channel('coco.decide.search.action.v1', 'decide.search',
            'coco.decide.v1.ActionBatch', True),
    Channel('coco.decide.search.observation.v1', 'decide.search',
            'coco.decide.v1.ObservationBatch', True),
    Channel('coco.mission.fsm.header.v1', 'mission.fsm',
            'coco.mission.v1.MissionHeader', False),
    Channel('coco.mission.fsm.transition.v1', 'mission.fsm',
            'coco.mission.v1.TransitionBatch', True),
    Channel('coco.sensor.detect.colour.v1', 'sensor.detect',
            'coco.sensor.v1.DetectionBatch', True),
    Channel('coco.arm.state.v1', 'arm', 'coco.arm.v1.ArmStateBatch', True),
)

#: The families README section 5.2 / M1.1 asks for in M1.
M1_FAMILIES = ('world', 'robot', 'truth', 'sensor.scan', 'plan.search',
               'plan.incremental', 'plan.path', 'input', 'metrics',
               'annotation')
#: The families M2.1 adds (docs/v2/M2_PROMPT.md).
M2_FAMILIES = ('estimate', 'localise.particles', 'localise.ekf', 'map.grid',
               'map.slam', 'control.local', 'decide.search', 'mission.fsm',
               'sensor.detect', 'arm')
FAMILIES = M1_FAMILIES + M2_FAMILIES

BY_NAME = {c.name: c for c in CHANNELS}


def parse(name: str):
    """
    Split a channel name into ``(family, name, major)``; raise if invalid.

    The family is the longest known family the name starts with (families
    may have two parts, ``plan.search``), and exactly one name part follows.
    """
    m = NAME.match(name)
    if not m:
        raise ValueError(f'not a coco channel name: {name!r}')
    body = m.group('body')
    for fam in sorted(FAMILIES + ('envelope',), key=len, reverse=True):
        rest = body[len(fam) + 1:]
        if body.startswith(fam + '.') and rest and '.' not in rest:
            return fam, rest, int(m.group('major'))
    raise ValueError(f'unknown family, or not one name part, in {name!r}')


def load_generated():
    """Import every generated module, so each message is registered."""
    import importlib
    import pkgutil
    from . import gen
    for info in pkgutil.walk_packages(gen.__path__, gen.__name__ + '.'):
        importlib.import_module(info.name)


def message_class(full_name: str):
    """Return the generated Python class for a fully qualified message."""
    from google.protobuf import symbol_database
    load_generated()
    return symbol_database.Default().GetSymbol(full_name)
