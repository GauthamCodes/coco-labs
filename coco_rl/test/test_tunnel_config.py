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
The remote-session tunnel exposes the platform's two paths and nothing else.

Phase 2 Part C3, owner's choice Tailscale Funnel (docs/live/tunnel/). These
are static checks on the committed configuration; the live external check
is ``docs/live/tunnel/external_check.sh``. Each guards one property the
README claims, so a convenient edit that widens the exposure fails here.
"""

import json
import pathlib

import pytest

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
TS = REPO / 'docs' / 'live' / 'tunnel' / 'tailscale'


def _compose():
    yaml = pytest.importorskip('yaml')
    return yaml.safe_load(
        (TS / 'docker-compose.tunnel-tailscale.yml').read_text())


def _serve():
    return json.loads((TS / 'serve.json').read_text())


def test_funnel_serves_exactly_ws_and_healthz_to_the_platform():
    """Two handlers, each proxying its own path on coco:8080."""
    web = _serve()['Web']
    assert list(web) == ['${TS_CERT_DOMAIN}:443']
    handlers = web['${TS_CERT_DOMAIN}:443']['Handlers']
    assert handlers == {
        '/ws': {'Proxy': 'http://coco:8080/ws'},
        '/healthz': {'Proxy': 'http://coco:8080/healthz'},
    }


def test_funnel_is_on_for_443_only_and_nothing_raw_is_forwarded():
    """No TCP forwarder: 443 terminates HTTPS, and only it is public."""
    serve = _serve()
    assert serve['TCP'] == {'443': {'HTTPS': True}}
    assert serve['AllowFunnel'] == {'${TS_CERT_DOMAIN}:443': True}
    for entry in serve['TCP'].values():
        assert 'TCPForward' not in entry


def test_the_sidecar_publishes_nothing_and_touches_no_host_surface():
    """No ports, no host network, no Docker socket, no privilege."""
    svc = _compose()['services']['tunnel']
    assert 'ports' not in svc and 'expose' not in svc
    assert svc.get('network_mode') is None
    assert 'privileged' not in svc
    assert svc['cap_drop'] == ['ALL'] and 'cap_add' not in svc
    assert 'no-new-privileges:true' in svc['security_opt']
    assert not str(svc['user']).startswith('0')
    mounts = ' '.join(svc['volumes'])
    assert 'docker.sock' not in mounts
    assert '/config/serve.json:ro' in mounts


def test_the_node_is_userspace_tagged_and_runs_no_ssh_server():
    """
    No TUN device, no Tailscale SSH, one granted tag.

    Not --shields-up: Tailscale refuses to turn Funnel on while it is set
    (measured, 2026-10-03), so the sidecar exited and nothing was served.
    """
    env = _compose()['services']['tunnel']['environment']
    assert env['TS_USERSPACE'] == 'true'
    assert env['TS_SERVE_CONFIG'] == '/config/serve.json'
    args = env['TS_EXTRA_ARGS'].split()
    assert '--shields-up' not in args
    assert not any(a.startswith('--ssh') for a in args)
    assert '--advertise-tags=tag:coco-live' in args
    # Each start asserts exactly this configuration, nothing left in state.
    assert '--reset' in args


def test_the_tailscale_image_is_pinned():
    """A version, not a moving tag: the configuration was tested on it."""
    image = _compose()['services']['tunnel']['image']
    assert image.startswith('tailscale/tailscale:')
    assert 'v1.' in image and 'latest' not in image and 'stable' not in image
