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

"""The v1 site as a built artifact (M3.0): assemble, verify, compare."""

import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import v1_site as V  # noqa: E402

CSP = (f"default-src 'self'; script-src 'self' 'wasm-unsafe-eval' {V.CDN}; "
       f"connect-src 'self' {V.CDN} ws://localhost:*; worker-src 'self'")


def write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb' if isinstance(data, bytes) else 'w') as f:
        f.write(data)


@pytest.fixture
def parts(tmp_path):
    dist = tmp_path / 'dist'
    write(str(dist / 'index.html'), f'<meta http-equiv="Content-Security-Policy" content="{CSP}"/><script src="/coco-labs/v1/assets/index.js"></script>')
    write(str(dist / 'assets/index.js'), f'var Dt=`{V.CDN}`;console.log(1)')
    write(str(dist / 'assets/other.js'), 'var x=1')
    write(str(dist / 'generated/catalog.json'), json.dumps({'a': 1, 'provenance': {'created_utc': '2026-10-10T00:00:00Z'}}))
    py = tmp_path / 'pyodide'
    for n in V.CORE_FILES:
        if n != 'pyodide-lock.json':
            write(str(py / n), f'core {n}')
    wheel = b'micropip wheel bytes'
    lock = {'info': {}, 'packages': {'micropip': {'file_name': 'micropip-0.11.1-py3-none-any.whl',
                                                  'sha256': hashlib.sha256(wheel).hexdigest(), 'depends': []}}}
    write(str(py / 'pyodide-lock.json'), json.dumps(lock))
    write(str(py / 'package.json'), json.dumps({'version': V.PYODIDE_VERSION}))
    wheels = tmp_path / 'wheels'
    write(str(wheels / 'micropip-0.11.1-py3-none-any.whl'), wheel)
    return dist, py, wheels, tmp_path


def test_assemble_self_hosts_pyodide_and_rewrites_only_the_cdn_url(parts):
    dist, py, wheels, tmp = parts
    out = str(tmp / 'site')
    m = V.assemble(str(dist), out, str(py), str(wheels))
    for n in list(V.CORE_FILES) + ['micropip-0.11.1-py3-none-any.whl']:
        assert os.path.isfile(os.path.join(out, 'pyodide', n))
    js = open(os.path.join(out, 'assets/index.js')).read()
    assert V.CDN not in js and f'`{V.SELF_HOSTED}`' in js
    html = open(os.path.join(out, 'index.html')).read()
    assert V.CDN not in html and "script-src 'self' 'wasm-unsafe-eval';" in html and "connect-src 'self' ws://" in html
    # nothing else changed
    assert open(os.path.join(out, 'assets/other.js')).read() == 'var x=1'
    assert {r['file'] for r in m['rewrites']} == {'index.html', 'assets/index.js'}
    assert m['source_commit'] == V.SOURCE_COMMIT and m['pyodide']['version'] == V.PYODIDE_VERSION


def test_assemble_refuses_a_wheel_that_is_not_the_locks(parts):
    dist, py, wheels, tmp = parts
    write(str(wheels / 'micropip-0.11.1-py3-none-any.whl'), b'tampered')
    with pytest.raises(SystemExit, match='sha256'):
        V.assemble(str(dist), str(tmp / 'site'), str(py), str(wheels))


def test_assemble_refuses_another_pyodide_version(parts):
    dist, py, wheels, tmp = parts
    write(str(py / 'package.json'), json.dumps({'version': '0.0.1'}))
    with pytest.raises(SystemExit, match='pins'):
        V.assemble(str(dist), str(tmp / 'site'), str(py), str(wheels))


def test_assemble_refuses_a_build_without_the_cdn_url(parts):
    dist, py, wheels, tmp = parts
    write(str(dist / 'assets/index.js'), 'var Dt=`elsewhere`')
    with pytest.raises(SystemExit, match='expected the CDN URL'):
        V.assemble(str(dist), str(tmp / 'site'), str(py), str(wheels))


def test_verify_passes_then_catches_a_changed_an_added_and_a_missing_file(parts):
    dist, py, wheels, tmp = parts
    out = str(tmp / 'site')
    m = V.assemble(str(dist), out, str(py), str(wheels))
    assert V.verify(out, m['tree_sha256'])['ok']
    assert not V.verify(out, '0' * 64)['ok']
    write(os.path.join(out, 'assets/other.js'), 'var x=2')
    write(os.path.join(out, 'extra.txt'), 'x')
    os.remove(os.path.join(out, 'pyodide/python_stdlib.zip'))
    r = V.verify(out)
    assert not r['ok']
    assert set(r['problems']) == {'changed: assets/other.js', 'not listed: extra.txt', 'missing: pyodide/python_stdlib.zip'}


def test_compare_ignores_only_created_utc(parts):
    dist, py, wheels, tmp = parts
    a = str(tmp / 'a')
    V.assemble(str(dist), a, str(py), str(wheels))
    write(str(dist / 'generated/catalog.json'), json.dumps({'a': 1, 'provenance': {'created_utc': '2027-01-01T00:00:00Z'}}))
    b = str(tmp / 'b')
    V.assemble(str(dist), b, str(py), str(wheels))
    r = V.compare(a, b)
    assert r['same_content'] and r['differ'] == [{'file': 'generated/catalog.json', 'only_created_utc': True}]
    write(os.path.join(b, 'generated/catalog.json'), json.dumps({'a': 2, 'provenance': {'created_utc': 'x'}}))
    assert not V.compare(a, b)['same_content']


def test_tree_hash_is_order_independent():
    assert V.tree_hash('b  2\na  1\n') == V.tree_hash('a  1\nb  2\n')
