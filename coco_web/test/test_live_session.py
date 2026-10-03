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
Remote sessions through the REAL handler, on real sockets (Phase 2 Part C).

control.py's policy is proved on its own in test_control.py. These prove
the server applies it: the gate sits in front of dispatch, a refusal
publishes nothing, every ending reaches the latched STOP, the host's
switches work, and ``remote:=true`` serves only ``/ws`` and ``/healthz``.
Time is a fake clock wherever idle or the cap matters; nothing sleeps for
it.
"""

import asyncio
import json

from coco_web import control
from coco_web import platform_server as ps
import pytest
from test_platform_server import FakeNode, Harness
from tornado.httpclient import AsyncHTTPClient, HTTPClientError, HTTPRequest
from tornado.websocket import websocket_connect

CODE = 'ABCD2345'
PAGES = 'https://gauthamcodes.github.io'
ORIGINS = f'{PAGES},http://localhost:*,http://127.0.0.1:*'


class FakeClock:
    """A monotonic clock that moves only when told."""

    def __init__(self):
        """Start at an arbitrary time."""
        self.t = 5000.0

    def __call__(self):
        """Return the current time."""
        return self.t


class CodeNode(FakeNode):
    """A FakeNode configured as a remote, code-access platform."""

    def __init__(self, remote=True, **policy):
        """Configure code access, optionally remote, with the origins."""
        super().__init__()
        self.control_config = ps.control_config(
            access='code', remote=remote, origins=ORIGINS, **policy)


def fixed(h, clock=None, **policy):
    """Give the platform a session with a known code (and a fake clock)."""
    h.platform.control = control.ControlSession(
        access=control.ACCESS_CODE,
        policy=control.Policy(**policy) if policy else
        h.platform.control_config['policy'],
        clock=clock or FakeClock(), on_stop=h.platform._on_control_end,
        code=CODE)
    return h.platform.control


def moving(node):
    """Every intent that could move COCO, as the node recorded it."""
    return [p for p in node.published
            if p[0] in ('drive', 'goal', 'colour')
            or (p[0] == 'mode' and p[1] != 'stop')
            or p == ('mission', 'start')]


def stopped(node):
    """Whether the latched STOP ran: zero, held zeros, arbiter idle."""
    return (('stop',) in node.published and ('mode', 'stop') in node.published
            and any(p[0] == 'hold' for p in node.published))


async def frame(h, ws, body):
    """Send one frame and return the ack or error that answers it."""
    body = dict(body, id='x')
    ws.write_message(json.dumps(body))
    return await h.until(ws, lambda f: f.get('type') in ('ack', 'error')
                         and f.get('id') == 'x')


async def closed(ws, timeout=2.0):
    """Read until the server closes the socket; True if it did."""
    try:
        while True:
            raw = await asyncio.wait_for(ws.read_message(), timeout)
            if raw is None:
                return True
    except asyncio.TimeoutError:
        return False


def _run(coro):
    """Run one async test body on a fresh event loop."""
    return asyncio.run(coro)


# ── driver and spectators ──────────────────────────────────────────────

def test_only_the_driver_moves_coco_and_spectators_cannot_stop():
    """Claim, drive, and a spectator refused drive and STOP alike."""
    async def body():
        h = await Harness(CodeNode()).start()
        fixed(h)
        driver, watcher = await h.client(), await h.client()
        before = await frame(h, driver, {'type': 'drive', 'linear': 0.2,
                                         'angular': 0.0})
        claim = await frame(h, driver, {'type': 'claim', 'code': CODE})
        drove = await frame(h, driver, {'type': 'drive', 'linear': 0.2,
                                        'angular': 0.0})
        refused = [await frame(h, watcher, f) for f in (
            {'type': 'drive', 'linear': 0.3, 'angular': 0.0},
            {'type': 'stop'},
            {'type': 'set_mode', 'mode': 'stop'},
            {'type': 'nav_goal', 'x': 1.0, 'y': 0.0},
            {'type': 'mission', 'action': 'start'},
            {'type': 'claim', 'code': CODE},
            {'type': 'release'})]
        published = list(h.node.published)
        await h.stop()
        return before, claim, drove, refused, published
    before, claim, drove, refused, published = _run(body())
    assert before['code'] == 'spectator'
    assert claim['type'] == 'ack' and claim['command'] == 'claim'
    assert drove['type'] == 'ack'
    assert [r['code'] for r in refused] == [
        'spectator', 'spectator', 'spectator', 'spectator', 'spectator',
        'driver_present', 'spectator']
    # Exactly one drive reached the node -- the driver's -- and no STOP.
    assert [p for p in published if p[0] == 'drive'] == [('drive', 0.2, 0.0)]
    assert ('stop',) not in published


def test_a_wrong_code_is_refused_and_five_close_the_socket():
    """bad_code, then a hang-up at the policy's limit."""
    async def body():
        h = await Harness(CodeNode()).start()
        fixed(h)
        ws = await h.client()
        codes = []
        for _ in range(4):
            codes.append((await frame(h, ws, {'type': 'claim',
                                              'code': 'WRONG234'}))['code'])
        ws.write_message(json.dumps({'type': 'claim', 'code': 'WRONG234'}))
        hung_up = await closed(ws)
        await h.stop()
        return codes, hung_up
    codes, hung_up = _run(body())
    assert codes == ['bad_code'] * 4
    assert hung_up


def test_the_welcome_and_telemetry_say_who_drives_without_the_code():
    """platform.control carries driver_id to compare with welcome.you."""
    async def body():
        h = await Harness(CodeNode()).start()
        fixed(h)
        ws = await h.client()
        await frame(h, ws, {'type': 'claim', 'code': CODE})
        h.platform.tick()
        tele = await h.until(ws, lambda f: f.get('type') == 'telemetry')
        await h.stop()
        return ws.welcome, tele
    welcome, tele = _run(body())
    block = tele['platform']['control']
    assert block['access'] == 'code' and block['driver'] is True
    assert block['driver_id'] == welcome['you']
    assert CODE not in json.dumps(tele) and CODE not in json.dumps(welcome)
    assert 'claim' in welcome['commands'] and 'release' in welcome['commands']


# ── every ending stops COCO ────────────────────────────────────────────

def test_release_stops_coco():
    """Letting go is the latched STOP."""
    async def body():
        h = await Harness(CodeNode()).start()
        fixed(h)
        ws = await h.client()
        await frame(h, ws, {'type': 'claim', 'code': CODE})
        h.node.published.clear()
        reply = await frame(h, ws, {'type': 'release'})
        await h.stop()
        return reply, h
    reply, h = _run(body())
    assert reply['type'] == 'ack'
    assert stopped(h.node)
    assert h.platform.stop_latch.latched
    assert h.platform.control.driver is None


def test_idle_releases_and_stops_on_a_fake_clock():
    """No command for idle_s: tick releases the driver and stops COCO."""
    async def body():
        h = await Harness(CodeNode()).start()
        clock = FakeClock()
        fixed(h, clock, idle_s=60.0)
        ws = await h.client()
        await frame(h, ws, {'type': 'claim', 'code': CODE})
        h.node.published.clear()
        clock.t += 59.0
        h.platform.tick()
        early = list(h.node.published)
        clock.t += 1.0
        h.platform.tick()
        # Telemetry is a state stream, one frame in flight: the next tick
        # delivers the frame owed since the release.
        await asyncio.sleep(0.05)
        h.platform.tick()
        tele = await h.until(ws, lambda f: f.get('type') == 'telemetry'
                             and not f['platform']['control']['driver'])
        refused = await frame(h, ws, {'type': 'drive', 'linear': 0.1,
                                      'angular': 0.0})
        await h.stop()
        return early, tele, refused, h
    early, tele, refused, h = _run(body())
    assert ('stop',) not in early
    assert stopped(h.node)
    assert tele['platform']['control']['last_end'] == control.END_IDLE
    assert refused['code'] == 'spectator'


def test_a_running_mission_keeps_the_driver_past_idle():
    """The executive reporting a mission is activity; the cap still holds."""
    async def body():
        h = await Harness(CodeNode()).start()
        clock = FakeClock()
        fixed(h, clock, idle_s=60.0, cap_s=600.0)
        ws = await h.client()
        await frame(h, ws, {'type': 'claim', 'code': CODE})
        h.node.running_mission()
        h.platform.tick()                      # refresh sees the mission
        for _ in range(10):
            clock.t += 50.0
            h.platform.tick()
        kept = h.platform.control.driver is not None
        clock.t += 100.0
        h.platform.tick()
        await h.stop()
        return kept, h
    kept, h = _run(body())
    assert kept
    assert h.platform.control.over == control.END_EXPIRED
    assert ('mission', 'abort') in h.node.published


def test_the_driver_disconnecting_stops_coco():
    """A closed driver tab releases control and stops."""
    async def body():
        h = await Harness(CodeNode()).start()
        fixed(h)
        # A spectator stays, so this is not the last-client stop.
        driver, h.watcher = await h.client(), await h.client()
        await frame(h, driver, {'type': 'claim', 'code': CODE})
        h.node.published.clear()
        driver.close()
        await asyncio.sleep(0.2)
        await h.stop()
        return h
    h = _run(body())
    assert stopped(h.node)
    assert h.platform.control.driver is None


def test_the_cap_ends_the_session_closes_sockets_and_refuses_newcomers():
    """Expiry: stop, every socket closed, new connections refused."""
    async def body():
        h = await Harness(CodeNode()).start()
        clock = FakeClock()
        fixed(h, clock, cap_s=300.0)
        ws = await h.client()
        await frame(h, ws, {'type': 'claim', 'code': CODE})
        clock.t += 300.0
        h.platform.tick()
        hung_up = await closed(ws)
        late = await websocket_connect(f'ws://127.0.0.1:{h.port}/ws')
        first = json.loads(await late.read_message())
        late_closed = await closed(late)
        await h.stop()
        return hung_up, first, late_closed, h
    hung_up, first, late_closed, h = _run(body())
    assert stopped(h.node)
    assert hung_up
    assert first['type'] == 'error' and first['code'] == 'session_over'
    assert late_closed


# ── the host's switches ────────────────────────────────────────────────

def test_kill_stops_ends_voids_and_locks_everyone_out():
    """host_kill: COCO stopped, sockets closed, the old code claims nothing."""
    async def body():
        h = await Harness(CodeNode()).start()
        fixed(h)
        driver, watcher = await h.client(), await h.client()
        await frame(h, driver, {'type': 'claim', 'code': CODE})
        h.node.published.clear()
        ok, message = h.platform.host_kill()
        both = [await closed(driver), await closed(watcher)]
        again = await websocket_connect(f'ws://127.0.0.1:{h.port}/ws')
        first = json.loads(await again.read_message())
        code_ok, code_msg = h.platform.host_code()
        await h.stop()
        return ok, both, first, code_ok, code_msg, h
    ok, both, first, code_ok, code_msg, h = _run(body())
    assert ok and both == [True, True]
    assert stopped(h.node)
    assert first['code'] == 'session_over'
    assert h.platform.control.code is None
    assert not code_ok and 'session_new' in code_msg


def test_kill_aborts_a_running_mission():
    """The kill switch is the latched STOP: a mission is aborted."""
    node = CodeNode()
    h = Harness(node)
    fixed(h)
    node.running_mission()
    h.platform.host_kill()
    assert ('mission', 'abort') in node.published
    assert stopped(node)


def test_a_new_session_has_a_new_code_and_the_old_one_is_void():
    """host_new_session: a fresh code; the previous code is bad_code."""
    async def body():
        h = await Harness(CodeNode()).start()
        fixed(h)
        h.platform.host_kill()
        ok, message = h.platform.host_new_session()
        new_code = h.platform.control.code
        ws = await h.client()
        old = await frame(h, ws, {'type': 'claim', 'code': CODE})
        new = await frame(h, ws, {'type': 'claim', 'code': new_code})
        await h.stop()
        return ok, message, new_code, old, new
    ok, message, new_code, old, new = _run(body())
    assert ok and new_code and new_code != CODE and new_code in message
    assert old['code'] == 'bad_code'
    assert new['type'] == 'ack'


def test_a_new_session_over_a_live_one_stops_coco_first():
    """Replacing a live session ends it, which stops COCO."""
    node = CodeNode()
    h = Harness(node)
    fixed(h)
    h.platform.host_new_session()
    assert stopped(node)


# ── remote:=true serves /ws and /healthz only ──────────────────────────

@pytest.mark.parametrize('path', [
    '/', '/index.html', '/app.js', '/frame.js', '/api/session',
    '/api/metrics', '/video/camera', '/video/annotated', '/legacy.html',
    '/../../etc/passwd', '/.git/config', '/ws/../api/session'])
def test_remote_serves_nothing_but_ws_and_healthz(path):
    """Every other path is a 404 on a remote platform."""
    async def body():
        h = await Harness(CodeNode(remote=True)).start()
        try:
            await AsyncHTTPClient().fetch(
                f'http://127.0.0.1:{h.port}{path}')
            status = 200
        except HTTPClientError as exc:
            status = exc.code
        health = None
        try:
            health = await AsyncHTTPClient().fetch(
                f'http://127.0.0.1:{h.port}/healthz')
        except HTTPClientError as exc:
            health = exc.response
        await h.stop()
        return status, health
    status, health = _run(body())
    assert status == 404, path
    assert health.code in (200, 503)
    assert json.loads(health.body)['protocol'] == 'coco.v1'


@pytest.mark.parametrize('method,path', [
    ('GET', '/healthz'), ('GET', '/nope'), ('POST', '/nope'),
    ('GET', '/api/session'), ('DELETE', '/healthz')])
def test_remote_responses_carry_no_server_banner(method, path):
    """No tornado version on the public surface, 404s included."""
    async def body():
        h = await Harness(CodeNode(remote=True)).start()
        try:
            resp = await AsyncHTTPClient().fetch(
                f'http://127.0.0.1:{h.port}{path}', method=method,
                body=b'' if method == 'POST' else None,
                raise_error=False)
        finally:
            await h.stop()
        return resp
    resp = _run(body())
    assert 'Server' not in resp.headers, (method, path, resp.headers)
    assert b'tornado' not in (resp.body or b'').lower()
    if path != '/healthz':
        assert resp.code == 404


def test_a_local_platform_still_serves_the_page():
    """remote:=false (default) keeps every route, as before."""
    async def body():
        h = await Harness(CodeNode(remote=False)).start()
        try:
            await AsyncHTTPClient().fetch(
                f'http://127.0.0.1:{h.port}/api/session')
            status = 200
        except HTTPClientError as exc:
            status = exc.code
        await h.stop()
        return status
    assert _run(body()) == 200


# ── origins ────────────────────────────────────────────────────────────

@pytest.mark.parametrize('origin,admitted', [
    (PAGES, True), ('http://localhost:4173', True),
    ('http://127.0.0.1:8080', True), ('https://evil.example', False),
    ('https://gauthamcodes.github.io.evil.example', False), ('null', False)])
def test_the_socket_admits_only_allowlisted_origins(origin, admitted):
    """A refused origin gets 403 at the handshake."""
    async def body():
        h = await Harness(CodeNode()).start()
        request = HTTPRequest(f'ws://127.0.0.1:{h.port}/ws',
                              headers={'Origin': origin})
        try:
            ws = await websocket_connect(request)
            welcome = json.loads(await ws.read_message())
            ok = welcome['type'] == 'welcome'
            ws.close()
        except HTTPClientError as exc:
            ok = 'refused' if exc.code == 403 else exc.code
        await h.stop()
        return ok
    assert _run(body()) == (True if admitted else 'refused')


@pytest.mark.parametrize('origin,cors', [
    (PAGES, True), ('http://localhost:5173', True),
    ('https://evil.example', False), (None, False)])
def test_healthz_is_readable_cross_origin_only_by_the_allowlist(origin, cors):
    """The public site may read /healthz; no other origin is told it may."""
    async def body():
        h = await Harness(CodeNode()).start()
        fixed(h)
        headers = {'Origin': origin} if origin else {}
        try:
            resp = await AsyncHTTPClient().fetch(
                f'http://127.0.0.1:{h.port}/healthz', headers=headers)
        except HTTPClientError as exc:
            resp = exc.response
        await h.stop()
        return resp
    resp = _run(body())
    allow = resp.headers.get('Access-Control-Allow-Origin')
    assert (allow == origin) if cors else allow is None
    live = json.loads(resp.body)['live']
    assert live['access'] == 'code' and live['over'] is None
    assert CODE not in resp.body.decode()
    assert 'driver_id' not in live


# ── open access is unchanged ───────────────────────────────────────────

def test_open_access_refuses_claims_and_lets_anyone_stop():
    """The local default: no code, STOP from anyone, as P0.1."""
    async def body():
        h = await Harness(FakeNode()).start()
        a, b = await h.client(), await h.client()
        claim = await frame(h, a, {'type': 'claim', 'code': CODE})
        stop = await frame(h, b, {'type': 'stop'})
        h.platform.tick()
        tele = await h.until(a, lambda f: f.get('type') == 'telemetry')
        await h.stop()
        return claim, stop, tele
    claim, stop, tele = _run(body())
    assert claim['code'] == 'open_access'
    assert stop['type'] == 'ack'
    assert tele['platform']['control'] == {'access': 'open', 'role': 'open',
                                           'over': None}


# ── configuration refuses unsafe combinations ──────────────────────────

@pytest.mark.parametrize('kwargs', [
    {'access': 'opne'}, {'access': ''}, {'remote': True},
    {'remote': True, 'access': 'open'}, {'remote': 'maybe', 'access': 'code'},
    {'remote': True, 'access': 'code'},
    {'remote': True, 'access': 'code', 'origins': '*'},
    {'remote': True, 'access': 'code', 'origins': ' , '},
    {'access': 'code', 'idle_s': 0}, {'access': 'code', 'max_clients': 0}])
def test_control_config_refuses_unsafe_or_broken_settings(kwargs):
    """A typo must not run an OPEN session on the public internet."""
    with pytest.raises(ValueError):
        ps.control_config(**kwargs)


def test_control_config_reads_launch_strings():
    """Launch arguments arrive as strings; they are read, not trusted."""
    config = ps.control_config(access='CODE', remote='true',
                               idle_s='45', cap_s='900', max_clients='10',
                               origins=ORIGINS)
    assert config['access'] == 'code' and config['remote'] is True
    assert config['policy'].idle_s == 45.0
    assert config['policy'].max_clients == 10
    assert PAGES in config['origins']
