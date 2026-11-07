"""R3.1: the committed COCO-Bench v1 datasheets are what tools/r3/make_datasheets.py writes."""
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]


def test_datasheets_are_current():
    r = subprocess.run([sys.executable, '-P', str(REPO / 'tools/r3/make_datasheets.py'), '--check'],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
