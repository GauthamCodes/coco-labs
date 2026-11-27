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
"""R5.4: coco_lab._xml (Pyodide has no xml) gives worldgen the standard library's SDF exactly."""
from pathlib import Path
import xml.etree.ElementTree as StdET

from coco_lab import _xml, worldgen
from coco_lab import worldspec_v3 as v3
from coco_lab.worldspec import normalize
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = (REPO / 'gazebo_models/worlds/coco_navigation.world').read_text(encoding='utf-8')
SPECS = sorted(p for p in (REPO / 'worlds').glob('*.yaml'))


def _with(et, fn, *a, **k):
    old = worldgen.ET
    worldgen.ET = et
    try:
        return fn(*a, **k)
    finally:
        worldgen.ET = old


@pytest.mark.parametrize('path', SPECS, ids=[p.stem for p in SPECS])
def test_sdf_world_identical(path):
    s = normalize(yaml.safe_load(path.read_text(encoding='utf-8')))
    std = _with(StdET, worldgen.sdf_world, s, TEMPLATE, world_name=s['id'])
    shim = _with(_xml, worldgen.sdf_world, s, TEMPLATE, world_name=s['id'])
    assert shim[0] == std[0]
    assert shim[1] == std[1]
    if v3.is_v3(s):
        for o in v3.objects(s):
            assert _with(_xml, worldgen.object_sdf, s, o['id']) == _with(
                StdET, worldgen.object_sdf, s, o['id']
            ), o['id']


def test_round_trip_and_escaping_match_the_standard_library():
    doc = (
        '<?xml version="1.0"?>\n<sdf version="1.9"><world name="a&amp;b"><model name="m">'
        '<pose>1 2 3</pose><static/>tail &lt;x&gt;</model><e attr=\'q"t\'></e></world></sdf>'
    )
    for et in (StdET, _xml):
        r = et.fromstring(doc)
        w = r.find('world')
        et.SubElement(w, 'added', name='n\t"<&>').text = 'a & b < c'
        et.indent(r, space='  ')
        if et is StdET:
            want = et.tostring(r, encoding='unicode')
        else:
            assert et.tostring(r, encoding='unicode') == want
    assert _xml.fromstring(doc).findall('.//model/pose')[0].text == '1 2 3'


@pytest.mark.parametrize('bad', ['<a><b></a>', '<a></a><b/>', 'x<a/>', '<a>&nope;</a>'])
def test_malformed_documents_are_refused(bad):
    with pytest.raises(ValueError):
        _xml.fromstring(bad)
