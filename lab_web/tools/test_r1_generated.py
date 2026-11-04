# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""R1: the committed generated files are what their generators make today."""
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def run(script, *args):
    return subprocess.run([sys.executable, str(REPO / 'tools' / 'r1' / script), *args],
                          capture_output=True, text=True, cwd=REPO, timeout=600)


@pytest.mark.parametrize('script', ['build_meta.py', 'make_suites.py', 'bench_readmes.py', 'build_datasets.py'])
def test_generated_file_is_current(script):
    """meta.json (the builder's tables), the frozen COCO-Bench suites, their READMEs, the datasets index."""
    r = run(script, '--check')
    assert r.returncode == 0, r.stdout + r.stderr
