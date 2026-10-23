# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""M5.1 documents the failed source check without touching the v1 archive."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_failed_v1_job_is_explicitly_disabled_and_explained():
    workflow = (ROOT / '.github/workflows/v1_reproducible.yml').read_text()
    assert 'if: ${{ false }}' in workflow
    assert 'V1_WORKFLOW.md' in workflow
    assert 'v1_site.py compare' in workflow
    assert (ROOT / 'docs/v2/data/m5/defects/V1_WORKFLOW.md').exists()
