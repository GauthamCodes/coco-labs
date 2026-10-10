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
The 16 recorded searches replay byte for byte through the v2 pipeline (M2.7).

docs/v2/data/m2/m27/p05_matrix.mcap is Lab 4's 16 searches, recorded on the
full ROS 2 stack in Gazebo, converted to v2 channels by
lab_web/src/convert/lab4.ts (lab_web/test/convert_lab4.test.ts requires
that exact file from the committed bundle). Here, for every search, the
looks are read off the CONVERTED observation channel alone, coco_lab's
regionsearch.replay_search chooses every bay again from them, and the
channels are re-encoded from that recomputed trace (with the Python
protobuf classes) and must equal the file's messages, byte for byte.
Simulator times are inputs (the recording's), read off the file; every
belief, candidate cost, choice, outcome and cost is recomputed.
"""

import json
import os

from coco_lab import regionsearch as rs
from coco_lab.columns import Batch
from coco_schemas.channels import message_class
from coco_schemas.mcap_read import McapError, read_messages
import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RUN = os.path.join(REPO, 'docs', 'v2', 'data', 'm2', 'm27', 'p05_matrix.mcap')
CH = {'header': 'coco.decide.search.header.v1',
      'belief': 'coco.decide.search.belief.v1',
      'action': 'coco.decide.search.action.v1',
      'observation': 'coco.decide.search.observation.v1',
      'transition': 'coco.mission.fsm.transition.v1',
      'metrics': 'coco.metrics.values.v1'}
OUTCOME = {1: 'found', 0: 'miss', -1: ''}


def encode(batch: Batch) -> bytes:
    cols, scalars = batch.drain()
    msg = message_class(batch.message)()
    for name, values in cols.items():
        getattr(msg, name).extend(list(values))
    for name, value in scalars.items():
        setattr(msg, name, value)
    return msg.SerializeToString(deterministic=True)


def channels_of(run_id, problem, trace, times):
    """Return the converter's channels for one search, as stated here."""
    n = problem.n
    ids = problem.ids
    out = {k: [] for k in CH}
    batches = {
        'transition': Batch('coco.mission.v1.TransitionBatch',
                            mission_id=run_id),
        'belief': Batch('coco.decide.v1.BeliefBatch', problem_id=run_id),
        'action': Batch('coco.decide.v1.ActionBatch', problem_id=run_id),
        'observation': Batch('coco.decide.v1.ObservationBatch',
                             problem_id=run_id),
        'metrics': Batch('coco.metrics.v1.MetricBatch'),
    }
    prev = ''
    for k in range(trace.n_events):
        t = times[k]
        kind = rs.KINDS[trace.kind[k]]
        reg = trace.region[k]
        b = batches['transition']
        b.add(k, t, from_state=prev, to_state=kind, event=kind,
              reason=ids[reg] if reg >= 0 else '',
              result=OUTCOME[trace.outcome[k]])
        out['transition'].append(encode(b))
        prev = kind
        b = batches['belief']
        b.scalars['update'] = k
        for i in range(n):
            b.add(k, t, region=i, probability=trace.belief[k * n + i])
        out['belief'].append(encode(b))
        if kind == 'select':
            b = batches['action']
            b.scalars['update'] = k
            for i in range(n):
                b.add(k, t, region=i,
                      expected_cost=trace.candidates[k * n + i],
                      reason='chosen' if i == reg else 'candidate')
            out['action'].append(encode(b))
        if kind == 'survey':
            b = batches['observation']
            b.add(k, t, region=reg, found=trace.outcome[k] == 1)
            out['observation'].append(encode(b))
        b = batches['metrics']
        b.add(k, t, name=f'{run_id}.cost', value=trace.cost[k], unit='m')
        out['metrics'].append(encode(b))
    return out


@pytest.fixture(scope='module')
def run():
    with open(RUN, 'rb') as f:
        msgs = read_messages(f.read())
    man = message_class('coco.envelope.v1.Manifest')()
    man.ParseFromString(msgs[0].data)
    return man, msgs[1:]


def by_search(msgs, name, key):
    cls = message_class(name)
    out = {}
    for m in msgs:
        if m.schema != name:
            continue
        msg = cls()
        msg.ParseFromString(m.data)
        out.setdefault(getattr(msg, key), []).append((m, msg))
    return out


def test_the_file_is_the_stack_recording(run):
    man, msgs = run
    assert man.spec_format == 'coco_lab.search_bundle.v1+json'
    assert man.evidence_class == 2  # EVIDENCE_CLASS_STACK
    spec = json.loads(man.spec)
    assert len(spec['runs']) == 16
    assert all(r['kind'] == 'recorded' for r in spec['runs'])


def test_the_16_searches_replay_byte_for_byte(run):
    man, msgs = run
    spec = json.loads(man.spec)
    problem = rs.SearchProblem.from_dict(spec['problem'])
    heads = by_search(msgs, 'coco.decide.v1.SearchProblemHeader',
                      'problem_id')
    obs = by_search(msgs, 'coco.decide.v1.ObservationBatch', 'problem_id')
    trans = by_search(msgs, 'coco.mission.v1.TransitionBatch', 'mission_id')
    beliefs = by_search(msgs, 'coco.decide.v1.BeliefBatch', 'problem_id')
    actions = by_search(msgs, 'coco.decide.v1.ActionBatch', 'problem_id')
    metrics = {}
    for m in msgs:
        if m.schema == 'coco.metrics.v1.MetricBatch':
            msg = message_class(m.schema)()
            msg.ParseFromString(m.data)
            metrics.setdefault(msg.name[0][:-len('.cost')], []).append(m)
    assert len(heads) == 16
    replayed = 0
    for run_id, [(_, head)] in heads.items():
        params = {p.key: p.value.string_value for p in head.params.items}
        given = [problem.index(r) for r in params['given_order'].split(',')
                 if r]
        looks = [(problem.ids[o.region[0]], bool(o.found[0]))
                 for _, o in sorted(obs.get(run_id, []),
                                    key=lambda x: x[1].tick[0])]
        trace = rs.replay_search(problem, params['policy'], looks, given)
        times = [t.t_world[0] for _, t in sorted(
            trans[run_id], key=lambda x: x[1].tick[0])]
        assert len(times) == trace.n_events
        want = channels_of(run_id, problem, trace, times)
        got = {'transition': [m.data for m, _ in trans[run_id]],
               'belief': [m.data for m, _ in beliefs[run_id]],
               'action': [m.data for m, _ in actions.get(run_id, [])],
               'observation': [m.data for m, _ in obs.get(run_id, [])],
               'metrics': [m.data for m in metrics[run_id]]}
        for k in CH:
            if k == 'header':
                continue
            assert got[k] == want[k], (run_id, k)
        replayed += 1
    assert replayed == 16


def test_a_changed_look_is_caught(run):
    # the check has teeth: flip one look and the replay no longer matches
    man, msgs = run
    spec = json.loads(man.spec)
    problem = rs.SearchProblem.from_dict(spec['problem'])
    obs = by_search(msgs, 'coco.decide.v1.ObservationBatch', 'problem_id')
    run_id = 'A1_fixed_red'
    looks = [(problem.ids[o.region[0]], bool(o.found[0]))
             for _, o in obs[run_id]]
    looks[0] = (looks[0][0], not looks[0][1])
    with pytest.raises(rs.SearchError, match='after the search ended'):
        rs.replay_search(problem, 'expected_cost', looks)


def test_a_compressed_file_is_refused():
    with pytest.raises(McapError):
        read_messages(b'not an mcap at all')
