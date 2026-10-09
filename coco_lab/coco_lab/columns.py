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
The whole loop's event batches as columns (M2.1; ADR 0001).

coco_lab never imports protobuf. Each M2 family's ``*Batch`` message in
``coco_schemas`` is declared here as a table: its repeated columns, in
field order, with an ``array`` typecode, and its per-batch scalars. A
:class:`Batch` fills one; the Web Worker posts the numeric columns as
transferable buffers (string and bool columns go as JSON), and TypeScript
encodes them only when a run is stored. ``coco_schemas`` tests that every
table here is exactly its message's fields -- names, order and kinds -- so
the emitter cannot drift from the schema.

Typecodes: ``Q`` uint64, ``d`` double, ``f`` float, ``I`` uint32, ``i``
(s)int32, ``B`` bool (stored 0/1), ``s`` string (a list, not an array).
"""

from array import array
from typing import Dict, List, Sequence, Tuple, Union

CLOCKS = (('seq', 'Q'), ('tick', 'Q'), ('t_world', 'd'))
COV = (('cov_xx', 'd'), ('cov_xy', 'd'), ('cov_xt', 'd'), ('cov_yy', 'd'),
       ('cov_yt', 'd'), ('cov_tt', 'd'))


def _cov(prefix: str):
    return tuple((prefix + n, t) for n, t in COV)


#: message -> (repeated columns after the clocks, per-batch scalars)
TABLES: Dict[str, Tuple[Tuple[Tuple[str, str], ...],
                        Tuple[Tuple[str, str], ...]]] = {
    'coco.estimate.v1.EstimateBatch': (
        (('x', 'd'), ('y', 'd'), ('theta', 'd')) + COV,
        (('estimator', 's'),)),
    'coco.localise.v1.ParticleSetBatch': (
        (('x', 'd'), ('y', 'd'), ('theta', 'd'), ('weight', 'd')),
        (('update', 'Q'), ('filter_id', 's'))),
    'coco.localise.v1.ParticleUpdateBatch': (
        (('update', 'Q'), ('n_eff', 'd'), ('resampled', 'B'),
         ('injected', 'I'), ('p_inject', 'd'), ('w_avg', 'd'),
         ('w_slow', 'd'), ('w_fast', 'd'), ('cluster_weight', 'd')),
        (('filter_id', 's'),)),
    'coco.localise.v1.EkfUpdateBatch': (
        (('update', 'Q'), ('pred_x', 'd'), ('pred_y', 'd'),
         ('pred_theta', 'd')) + _cov('pred_')
        + (('post_x', 'd'), ('post_y', 'd'), ('post_theta', 'd'))
        + _cov('post_')
        + (('beams_used', 'I'), ('beams_gated', 'I'), ('nis', 'd')),
        (('filter_id', 's'),)),
    'coco.map.v1.MapCellBatch': (
        (('row', 'I'), ('col', 'I'), ('logodds', 'f')),
        (('update', 'Q'), ('map_id', 's'))),
    'coco.map.v1.LandmarkBatch': (
        (('landmark_id', 'I'), ('x', 'd'), ('y', 'd'), ('cov_xx', 'd'),
         ('cov_xy', 'd'), ('cov_yy', 'd')),
        (('update', 'Q'), ('slam_id', 's'))),
    'coco.map.v1.SlamParticleBatch': (
        (('x', 'd'), ('y', 'd'), ('theta', 'd'), ('weight', 'd')),
        (('best', 'I'), ('update', 'Q'), ('slam_id', 's'))),
    'coco.map.v1.GraphNodeBatch': (
        (('node_id', 'I'), ('x', 'd'), ('y', 'd'), ('theta', 'd')),
        (('stage', 's'), ('chi2', 'd'), ('slam_id', 's'))),
    'coco.map.v1.GraphEdgeBatch': (
        (('from_node', 'I'), ('to_node', 'I'), ('kind', 's'), ('dx', 'd'),
         ('dy', 'd'), ('dtheta', 'd'), ('error', 'd')),
        (('stage', 's'), ('slam_id', 's'))),
    'coco.control.v1.CandidateBatch': (
        (('candidate', 'I'), ('v', 'd'), ('w', 'd'), ('valid', 'B'),
         ('rejection', 's'), ('cost', 'd'), ('critic_scores', 'd'),
         ('traj_offset', 'I'), ('traj_len', 'I'), ('traj_x', 'd'),
         ('traj_y', 'd')),
        (('cycle', 'Q'), ('controller_id', 's'))),
    'coco.control.v1.CommandBatch': (
        (('cycle', 'Q'), ('chosen', 'i'), ('v', 'd'), ('w', 'd'),
         ('status', 's'), ('n_candidates', 'I'), ('n_valid', 'I'),
         ('lookahead_x', 'd'), ('lookahead_y', 'd')),
        (('controller_id', 's'),)),
    'coco.decide.v1.BeliefBatch': (
        (('region', 'I'), ('probability', 'd')),
        (('update', 'Q'), ('problem_id', 's'))),
    'coco.decide.v1.OrderCostBatch': (
        (('order_offset', 'I'), ('order_len', 'I'), ('order', 'I'),
         ('expected_cost', 'd')),
        (('update', 'Q'), ('problem_id', 's'))),
    'coco.decide.v1.ActionBatch': (
        (('region', 'I'), ('expected_cost', 'd'), ('reason', 's')),
        (('update', 'Q'), ('problem_id', 's'))),
    'coco.decide.v1.ObservationBatch': (
        (('region', 'I'), ('found', 'B')),
        (('problem_id', 's'),)),
    'coco.mission.v1.TransitionBatch': (
        (('from_state', 's'), ('to_state', 's'), ('event', 's'),
         ('reason', 's'), ('result', 's')),
        (('mission_id', 's'),)),
    'coco.sensor.v1.DetectionBatch': (
        (('region_id', 's'), ('colour', 's'), ('detected', 'B'),
         ('range', 'd'), ('bearing', 'd')),
        (('detection_probability', 'd'), ('detection_label', 's'))),
    # M1's metrics batch: the whole loop's numbers (errors, ATE, F1, ...)
    'coco.metrics.v1.MetricBatch': (
        (('name', 's'), ('value', 'd'), ('unit', 's')),
        ()),
    'coco.arm.v1.ArmStateBatch': (
        (('joint1', 'd'), ('joint2', 'd'), ('ee_x', 'd'), ('ee_z', 'd'),
         ('finger_left', 'd'), ('finger_right', 'd'), ('magnet_on', 'B'),
         ('holding', 'B'), ('phase', 's')),
        ()),
}

#: Columns whose rows are not one-per-event: the flattened lists of
#: CandidateBatch and OrderCostBatch (their own lengths, see the protos).
FLAT = {'critic_scores', 'traj_x', 'traj_y', 'order'}

Column = Union[array, List]


class Batch:
    """One ``*Batch`` message being filled, as columns."""

    def __init__(self, message: str, **scalars):
        """Start empty; ``scalars`` are the message's per-batch fields."""
        if message not in TABLES:
            raise KeyError(f'no column table for {message!r}')
        self.message = message
        cols, sc = TABLES[message]
        self.fields = CLOCKS + cols
        known = {n for n, _ in sc}
        bad = set(scalars) - known
        if bad:
            raise KeyError(f'{message} has no scalar {sorted(bad)}')
        self.scalars = {n: scalars.get(n, '' if t == 's' else 0)
                        for n, t in sc}
        self.seq = 0
        self._new()

    def _new(self):
        self.columns: Dict[str, Column] = {
            n: ([] if t == 's' else array(t)) for n, t in self.fields}

    def __len__(self) -> int:
        """Return the number of rows (events) not yet drained."""
        return len(self.columns['seq'])

    def add(self, tick: int, t_world: float, **row) -> None:
        """Append one row; every per-event column must be given."""
        c = self.columns
        c['seq'].append(self.seq)
        c['tick'].append(tick)
        c['t_world'].append(t_world)
        for n, t in self.fields[3:]:
            if n in FLAT:
                continue
            v = row[n]
            c[n].append(int(bool(v)) if t == 'B' else v)
        self.seq += 1

    def extend_flat(self, name: str, values: Sequence) -> None:
        """Append to a flattened list column (``critic_scores``, ...)."""
        if name not in FLAT:
            raise KeyError(f'{name!r} is not a flattened column')
        self.columns[name].extend(values)

    def drain(self) -> Tuple[Dict[str, Column], Dict[str, object]]:
        """Return (columns, scalars) so far and start anew (seq continues)."""
        out = self.columns
        self._new()
        return out, dict(self.scalars)
