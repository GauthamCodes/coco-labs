"""R3.7: the site's "Cite" text (lab_web/src/shell/citation.ts) agrees with CITATION.cff."""
from pathlib import Path
import re

import yaml

REPO = Path(__file__).resolve().parents[2]


def test_cite_text_matches_citation_cff():
    cff = yaml.safe_load((REPO / 'CITATION.cff').read_text())
    ts = (REPO / 'lab_web' / 'src' / 'shell' / 'citation.ts').read_text()
    title = re.search(r"CITATION_TITLE =\s*'([^']+)'", ts).group(1)
    author = re.search(r"CITATION_AUTHOR = '([^']+)'", ts).group(1)
    url = re.search(r"CITATION_URL = '([^']+)'", ts).group(1)
    assert title == cff['title']
    assert author == cff['authors'][0]['given-names']
    assert url == cff['repository-code']
    assert cff['license'] == 'Apache-2.0'
