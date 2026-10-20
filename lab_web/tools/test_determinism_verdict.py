# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""A fresh Node result and final chains must participate in the verdict."""
import gzip
import json
from pathlib import Path
import subprocess

import pytest

HARNESS = Path(__file__).parent / 'perf' / 'determinism.mjs'


@pytest.mark.parametrize('change', ['none', 'hash', 'chain', 'page_error'])
def test_saved_reference_does_not_hide_fresh_node_failure(tmp_path, change):
    reference = tmp_path / 'reference'
    output = tmp_path / 'output'
    reference.mkdir()
    output.mkdir()
    sessions = tmp_path / 'sessions.json'
    sessions.write_text(json.dumps({'sessions': [{'id': 0, 'ticks': 1}]}))
    baseline = {'engine': 'pyodide-node', 'version': 'fixture', 'seconds': 0,
                'sessions': [{'id': 0, 'hashes': ['original'], 'chain': 'chain'}]}
    filename = 'hashes_pyodide-node.json.gz'
    (reference / filename).write_bytes(gzip.compress(json.dumps(baseline).encode()))
    fresh = json.loads(json.dumps(baseline))
    if change == 'hash':
        fresh['sessions'][0]['hashes'][0] = 'changed'
    elif change == 'chain':
        fresh['sessions'][0]['chain'] = 'changed'
    elif change == 'page_error':
        fresh['page_errors'] = ['worker failed']
    (output / filename).write_bytes(gzip.compress(json.dumps(fresh).encode()))
    result = subprocess.run(
        ['node', str(HARNESS), 'compare', '--sessions', str(sessions),
         '--out', str(output), '--ref', str(reference), '--engines', '1'],
        capture_output=True, text=True, check=False)
    report = json.loads((output / 'determinism.json').read_text())
    assert report['pass'] == (change == 'none')
    assert result.returncode == (0 if change == 'none' else 1)
