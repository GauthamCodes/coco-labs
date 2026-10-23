# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""Publication requires an owner-confirmed manual main run and every test job."""
from pathlib import Path
import re


def test_pages_gate():
    workflow = (Path(__file__).resolve().parents[2] / '.github/workflows/lab.yml').read_text()
    deploy = workflow.split('\n  deploy:\n')[1]
    expression = re.search(r'^    if: (.+)$', deploy, re.M).group(1)
    for event, ref, confirmation, expected in [
        ('push', 'refs/heads/main', 'DEPLOY', False),
        ('pull_request', 'refs/heads/main', 'DEPLOY', False),
        ('workflow_dispatch', 'refs/heads/v2/m5-focus', 'DEPLOY', False),
        ('workflow_dispatch', 'refs/heads/main', '', False),
        ('workflow_dispatch', 'refs/heads/main', 'DEPLOY', True),
    ]:
        actual = expression.replace('github.event_name', repr(event)).replace(
            'github.ref', repr(ref)).replace('inputs.confirmation', repr(confirmation))
        assert eval(actual.replace('&&', ' and '), {'__builtins__': {}}) is expected
    assert 'name: Deploy site' in deploy
    assert 'needs: [ coco-lab-venv, lab-web, lab-web-browsers ]' in deploy
    assert 'required: true' in workflow.split('  workflow_dispatch:')[1].split('\npermissions:')[0]
    assert 'branches: [ lab1, main ]' in workflow
