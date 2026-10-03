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
The driver / spectator policy (Phase 2 Part C), proved on a fake clock.

Nothing here sleeps: time is ``FakeClock.t`` and moves only when a test
moves it. Stopping the robot is a recording callback.
"""

import ast
import pathlib
import random

from coco_web import control
from coco_web import protocol
import pytest

CODE = 'ABCD2345'


class FakeClock:
    """A monotonic clock that moves only when told."""

    def __init__(self, t=1000.0):
        """Start at an arbitrary, non-zero time."""
        self.t = t

    def __call__(self):
        """Return the current time."""
        return self.t

    def advance(self, seconds):
        """Move time forward."""
        self.t += seconds


class Stops:
    """Record every on_stop call."""

    def __init__(self):
        """No stops yet."""
        self.reasons = []

    def __call__(self, reason):
        """Record one stop."""
        self.reasons.append(reason)


def make(access=control.ACCESS_CODE, **policy):
    """Build a session with a known code, a fake clock and a stop recorder."""
    clock, stops = FakeClock(), Stops()
    session = control.ControlSession(
        access=access, policy=control.Policy(**policy), clock=clock,
        on_stop=stops, code=CODE if access == control.ACCESS_CODE else None)
    return session, clock, stops


def joined(session, *ids):
    """Connect clients and assert each was admitted."""
    for cid in ids:
        assert session.connect(cid).ok
    return session


def claim(session, cid, code=CODE):
    """Present a code as `cid`."""
    return session.admit(cid, 'claim', {'code': code})


# ── driver acquire ─────────────────────────────────────────────────────

def test_the_right_code_makes_the_driver():
    """A client presenting the host's code becomes the one driver."""
    s, _clock, stops = make()
    joined(s, 'a')
    assert s.driver is None
    assert claim(s, 'a').ok
    assert s.driver == 'a'
    assert s.as_dict('a')['role'] == 'driver'
    assert stops.reasons == []


def test_the_code_is_normalised_but_not_guessed():
    """Spaces, dashes and case are forgiven; nothing else is."""
    s, _clock, _stops = make()
    joined(s, 'a')
    assert claim(s, 'a', 'abcd-2345 ').ok


def test_only_the_driver_commands():
    """After a claim, every command intent from the driver is admitted."""
    s, clock, _stops = make()
    joined(s, 'a')
    claim(s, 'a')
    for kind in sorted(control.COMMAND_INTENTS):
        clock.advance(1.0)                   # stay inside the rate limits
        assert s.admit('a', kind, {}).ok, kind


def test_no_driver_means_nobody_commands():
    """Before any claim, a command intent is refused, not let through."""
    s, _clock, _stops = make()
    joined(s, 'a')
    verdict = s.admit('a', 'drive', {'linear': 0.1, 'angular': 0.0})
    assert not verdict.ok
    assert verdict.code == 'spectator'


def test_host_generated_codes_are_well_formed_and_differ():
    """A default session draws a fresh code from the documented alphabet."""
    clock = FakeClock()
    codes = {control.ControlSession(control.ACCESS_CODE, clock=clock).code
             for _ in range(50)}
    assert len(codes) == 50
    for code in codes:
        assert len(code) == control.CODE_LENGTH
        assert set(code) <= set(control.CODE_ALPHABET)


def test_new_code_uses_an_injected_rng_deterministically():
    """The generator is testable; the default is secrets."""
    a = control.new_code(random.Random(7))
    b = control.new_code(random.Random(7))
    assert a == b and len(a) == control.CODE_LENGTH


# ── spectators ─────────────────────────────────────────────────────────

@pytest.mark.parametrize('kind', sorted(control.COMMAND_INTENTS))
def test_spectators_are_refused_every_command(kind):
    """While someone drives, every command from anyone else is refused."""
    s, _clock, stops = make()
    joined(s, 'driver', 'watcher')
    claim(s, 'driver')
    verdict = s.admit('watcher', kind, {'mode': 'stop'})
    assert not verdict.ok
    assert verdict.code == 'spectator'
    assert stops.reasons == []


def test_spectators_cannot_stop():
    """Owner decision 3: no STOP for spectators, in either spelling."""
    s, _clock, stops = make()
    joined(s, 'driver', 'watcher')
    claim(s, 'driver')
    assert s.admit('watcher', 'stop', {}).code == 'spectator'
    assert s.admit('watcher', 'set_mode', {'mode': 'stop'}).code == 'spectator'
    assert stops.reasons == []
    assert s.driver == 'driver'


@pytest.mark.parametrize('kind', sorted(control.READ_INTENTS))
def test_spectators_keep_telemetry_and_video(kind):
    """Read-only intents (subscriptions, ping) are admitted for anyone."""
    s, _clock, _stops = make()
    joined(s, 'driver', 'watcher')
    claim(s, 'driver')
    assert s.admit('watcher', kind, {}).ok


def test_an_unknown_intent_is_refused_not_waved_through():
    """A command type this policy was never told about fails closed."""
    s, _clock, _stops = make()
    joined(s, 'a')
    claim(s, 'a')
    assert not s.admit('a', 'teleport', {}).ok


def test_spectator_count_is_bounded():
    """Connections beyond max_clients are refused at connect."""
    s, _clock, _stops = make(max_clients=3)
    joined(s, 'a', 'b', 'c')
    verdict = s.connect('d')
    assert not verdict.ok and verdict.close and verdict.code == 'session_full'
    s.disconnect('c')
    assert s.connect('d').ok


def test_refusal_codes_are_part_of_the_protocol():
    """Every code this module returns is a coco.v1 refusal code, same text."""
    for code, text in control.REFUSALS.items():
        assert protocol.REFUSAL_CODES.get(code) == text, code


# ── duplicate driver / no implicit transfer ────────────────────────────

def test_a_second_claim_is_refused_while_a_driver_holds_control():
    """Even with the right code, a second client cannot take over."""
    s, _clock, stops = make()
    joined(s, 'a', 'b')
    claim(s, 'a')
    verdict = claim(s, 'b')
    assert not verdict.ok and verdict.code == 'driver_present'
    assert s.driver == 'a'
    assert stops.reasons == []


def test_reclaiming_as_the_driver_is_idempotent():
    """The driver presenting the code again keeps control."""
    s, _clock, _stops = make()
    joined(s, 'a')
    claim(s, 'a')
    assert claim(s, 'a').ok
    assert s.driver == 'a'


def test_control_never_passes_to_anyone_by_itself():
    """Release, idle and disconnect all leave NO driver, never another one."""
    for end in ('release', 'idle', 'disconnect'):
        s, clock, _stops = make()
        joined(s, 'a', 'b')
        claim(s, 'a')
        if end == 'release':
            assert s.admit('a', 'release', {}).ok
        elif end == 'idle':
            clock.advance(s.policy.idle_s)
            s.tick()
        else:
            s.disconnect('a')
        assert s.driver is None, end
        assert s.admit('b', 'drive', {}).code == 'spectator', end
        assert claim(s, 'b').ok, end
        assert s.driver == 'b', end


def test_a_spectator_cannot_release_the_driver():
    """Only the driver may let go."""
    s, _clock, stops = make()
    joined(s, 'a', 'b')
    claim(s, 'a')
    assert s.admit('b', 'release', {}).code == 'spectator'
    assert s.driver == 'a' and stops.reasons == []


def test_a_new_connection_of_the_same_person_must_claim_again():
    """Client ids are per connection: a reconnect is a spectator."""
    s, _clock, _stops = make()
    joined(s, 'a1')
    claim(s, 'a1')
    s.disconnect('a1')
    joined(s, 'a2')
    assert s.admit('a2', 'drive', {}).code == 'spectator'


# ── invalid / expired code ─────────────────────────────────────────────

@pytest.mark.parametrize('bad', ['WRONG234', '', None, 42, 'ABCD234',
                                 'ABCD23456', ' '])
def test_a_wrong_code_is_refused(bad):
    """Anything but the session's code is bad_code."""
    s, _clock, _stops = make()
    joined(s, 'a')
    verdict = s.admit('a', 'claim', {'code': bad})
    assert not verdict.ok and verdict.code == 'bad_code'
    assert s.driver is None


def test_repeated_wrong_codes_close_the_socket():
    """bad_code_limit wrong guesses, and the client is told to go."""
    s, _clock, _stops = make(bad_code_limit=3)
    joined(s, 'a')
    verdicts = [claim(s, 'a', 'WRONG234') for _ in range(3)]
    assert [v.close for v in verdicts] == [False, False, True]


def test_the_code_of_a_killed_session_is_void():
    """After kill the old code claims nothing."""
    s, _clock, _stops = make()
    joined(s, 'a')
    s.kill()
    assert s.code is None
    verdict = claim(s, 'a')
    assert not verdict.ok and verdict.code == 'session_over'


def test_the_code_of_an_expired_session_is_void():
    """After the cap the old code claims nothing."""
    s, clock, _stops = make(cap_s=100.0)
    joined(s, 'a')
    clock.advance(100.0)
    assert claim(s, 'a').code == 'session_over'
    assert s.code is None


def test_open_access_has_no_code_and_refuses_claims():
    """Open (local) access needs no code; a claim is answered open_access."""
    s, _clock, _stops = make(access=control.ACCESS_OPEN)
    assert s.code is None
    assert s.admit('a', 'claim', {'code': CODE}).code == 'open_access'


def test_open_access_admits_everything_like_p01():
    """Open access changes nothing: every intent from anyone, no limits."""
    s, _clock, stops = make(access=control.ACCESS_OPEN)
    for kind in sorted(control.COMMAND_INTENTS | control.READ_INTENTS):
        for _ in range(500):
            assert s.admit('anyone', kind, {}).ok
    assert s.connect('x').ok
    assert s.tick() is None
    assert stops.reasons == []


# ── idle timeout ───────────────────────────────────────────────────────

def test_idle_releases_the_driver_and_stops():
    """No command intent for idle_s: the driver is released, COCO stops."""
    s, clock, stops = make(idle_s=60.0)
    joined(s, 'a')
    claim(s, 'a')
    clock.advance(59.9)
    assert s.tick() is None and s.driver == 'a'
    clock.advance(0.1)
    assert s.tick() == control.END_IDLE
    assert s.driver is None
    assert stops.reasons == [control.END_IDLE]
    assert s.as_dict('a')['last_end'] == control.END_IDLE


def test_driver_commands_reset_the_idle_clock():
    """Driving is activity."""
    s, clock, stops = make(idle_s=60.0)
    joined(s, 'a')
    claim(s, 'a')
    for _ in range(10):
        clock.advance(50.0)
        assert s.admit('a', 'drive', {}).ok
        assert s.tick() is None
    assert s.driver == 'a' and stops.reasons == []


def test_pings_and_subscriptions_are_not_activity():
    """A background tab that only pings still times out."""
    s, clock, stops = make(idle_s=60.0)
    joined(s, 'a')
    claim(s, 'a')
    for _ in range(6):
        clock.advance(10.0)
        s.admit('a', 'ping', {})
        s.admit('a', 'subscribe', {})
        s.tick()
    assert s.driver is None and stops.reasons == [control.END_IDLE]


def test_running_autonomy_holds_the_lease():
    """A fetch runs for minutes untouched; autonomy keeps the driver."""
    s, clock, stops = make(idle_s=60.0)
    joined(s, 'a')
    claim(s, 'a')
    for _ in range(30):
        clock.advance(10.0)
        assert s.tick(busy=True) is None
    assert s.driver == 'a' and stops.reasons == []


def test_autonomy_is_not_driver_activity():
    """The lease is autonomy's, said so; the driver's input clock runs on."""
    s, clock, _stops = make(idle_s=60.0)
    joined(s, 'a')
    claim(s, 'a')
    clock.advance(5.0)
    s.tick(busy=True)
    clock.advance(295.0)
    s.tick(busy=True)
    block = s.as_dict('a')
    assert block['lease'] == control.LEASE_AUTONOMY
    assert block['idle_left_s'] is None
    assert block['last_input_s'] == pytest.approx(300.0)


def test_the_lease_returns_to_the_driver_with_a_full_window():
    """When autonomy ends, idle_s is counted from that moment, then stops."""
    s, clock, stops = make(idle_s=60.0)
    joined(s, 'a')
    claim(s, 'a')
    s.tick(busy=True)
    clock.advance(300.0)
    assert s.tick(busy=False) is None
    block = s.as_dict('a')
    assert block['lease'] == control.LEASE_DRIVER
    assert block['idle_left_s'] == pytest.approx(60.0)
    assert block['last_input_s'] == pytest.approx(300.0)
    clock.advance(59.0)
    assert s.tick(busy=False) is None and s.driver == 'a'
    clock.advance(1.0)
    assert s.tick(busy=False) == control.END_IDLE
    assert stops.reasons == [control.END_IDLE]


def test_a_command_after_autonomy_restarts_the_window():
    """Driver input after autonomy ended is the later of the two."""
    s, clock, _stops = make(idle_s=60.0)
    joined(s, 'a')
    claim(s, 'a')
    s.tick(busy=True)
    clock.advance(100.0)
    s.tick(busy=False)
    clock.advance(30.0)
    assert s.admit('a', 'drive', {}).ok
    clock.advance(59.0)
    assert s.tick() is None
    assert s.as_dict('a')['idle_left_s'] == pytest.approx(1.0)
    clock.advance(1.0)
    assert s.tick() == control.END_IDLE


def test_a_driver_without_autonomy_reports_the_driver_lease():
    """No autonomy: the lease is the driver's and the countdown runs."""
    s, clock, _stops = make(idle_s=60.0)
    joined(s, 'a')
    claim(s, 'a')
    clock.advance(10.0)
    s.tick(busy=False)
    block = s.as_dict('a')
    assert block['lease'] == control.LEASE_DRIVER
    assert block['idle_left_s'] == pytest.approx(50.0)
    assert block['last_input_s'] == pytest.approx(10.0)


def test_no_driver_no_lease():
    """With nobody driving there is no lease, whatever autonomy does."""
    s, clock, _stops = make(idle_s=60.0)
    joined(s, 'a')
    s.tick(busy=True)
    block = s.as_dict('a')
    assert block['lease'] is None and block['idle_left_s'] is None


def test_autonomy_history_does_not_carry_to_the_next_driver():
    """After control ends, a new driver's window starts at their claim."""
    s, clock, _stops = make(idle_s=60.0)
    joined(s, 'a', 'b')
    claim(s, 'a')
    s.tick(busy=True)
    clock.advance(100.0)
    s.tick(busy=False)
    s.admit('a', 'release', {})
    clock.advance(1.0)
    assert claim(s, 'b').ok
    clock.advance(60.0)
    assert s.tick() == control.END_IDLE


@pytest.mark.parametrize('busy', [None, 1, 'yes', 'True'])
def test_only_a_true_busy_is_busy(busy):
    """Unknown autonomy state is not busy: the idle clock runs (closed)."""
    s, clock, _stops = make(idle_s=60.0)
    joined(s, 'a')
    claim(s, 'a')
    clock.advance(60.0)
    assert s.tick(busy=busy) == control.END_IDLE


def test_idle_left_is_reported():
    """Telemetry tells the driver how long until idle release."""
    s, clock, _stops = make(idle_s=60.0)
    joined(s, 'a')
    claim(s, 'a')
    clock.advance(15.0)
    assert s.as_dict('a')['idle_left_s'] == pytest.approx(45.0)


# ── session cap ────────────────────────────────────────────────────────

def test_the_cap_ends_the_session_and_stops():
    """At cap_s the session is over, the driver gone, COCO stopped."""
    s, clock, stops = make(cap_s=1200.0, idle_s=10_000.0)
    joined(s, 'a', 'b')
    claim(s, 'a')
    clock.advance(1199.0)
    assert s.tick() is None and s.over is None
    clock.advance(1.0)
    assert s.tick() == control.END_EXPIRED
    assert s.over == control.END_EXPIRED
    assert s.driver is None
    assert stops.reasons == [control.END_EXPIRED]


def test_the_cap_holds_even_while_busy():
    """Autonomy keeps the driver past idle, never past the cap."""
    s, clock, stops = make(cap_s=300.0)
    joined(s, 'a')
    claim(s, 'a')
    clock.advance(300.0)
    assert s.tick(busy=True) == control.END_EXPIRED
    assert stops.reasons == [control.END_EXPIRED]


def test_an_expired_session_refuses_everything_that_controls():
    """After expiry: claims, commands and new connections are refused."""
    s, clock, stops = make(cap_s=100.0)
    joined(s, 'a')
    claim(s, 'a')
    clock.advance(100.0)
    s.tick()
    for kind in sorted(control.COMMAND_INTENTS):
        assert s.admit('a', kind, {}).code == 'session_over', kind
    assert claim(s, 'a').code == 'session_over'
    connect = s.connect('new')
    assert not connect.ok and connect.close
    assert stops.reasons == [control.END_EXPIRED]


def test_expiry_is_enforced_at_the_frame_even_without_a_tick():
    """A frame arriving after the cap is refused and stops COCO once."""
    s, clock, stops = make(cap_s=100.0)
    joined(s, 'a')
    claim(s, 'a')
    clock.advance(150.0)
    assert s.admit('a', 'drive', {}).code == 'session_over'
    assert stops.reasons == [control.END_EXPIRED]
    assert s.tick() is None
    assert stops.reasons == [control.END_EXPIRED]


def test_session_left_counts_down_to_zero():
    """Telemetry carries the remaining session time."""
    s, clock, _stops = make(cap_s=600.0)
    clock.advance(200.0)
    assert s.as_dict()['session_left_s'] == pytest.approx(400.0)
    clock.advance(1000.0)
    s.tick()
    assert s.as_dict()['session_left_s'] == 0.0


# ── rate limits ────────────────────────────────────────────────────────

def test_drive_is_rate_limited_per_client():
    """Past the drive burst at one instant, drive is refused rate_limited."""
    s, clock, _stops = make(drive_rate=20.0, drive_burst=20.0)
    joined(s, 'a')
    claim(s, 'a')
    verdicts = [s.admit('a', 'drive', {}) for _ in range(25)]
    assert all(v.ok for v in verdicts[:20])
    assert [v.code for v in verdicts[20:]] == ['rate_limited'] * 5
    clock.advance(0.1)                       # two tokens at 20 Hz
    assert s.admit('a', 'drive', {}).ok
    assert s.admit('a', 'drive', {}).ok
    assert s.admit('a', 'drive', {}).code == 'rate_limited'


def test_the_page_drive_loop_is_never_limited():
    """The page's own 10 Hz drive loop runs for a minute untouched."""
    s, clock, _stops = make()
    joined(s, 'a')
    claim(s, 'a')
    for _ in range(600):
        clock.advance(0.1)
        assert s.admit('a', 'drive', {}).ok


def test_commands_are_rate_limited():
    """Non-drive commands have their own, slower bucket."""
    s, _clock, _stops = make(command_rate=2.0, command_burst=3.0)
    joined(s, 'a')
    claim(s, 'a')                            # the claim takes a token too
    codes = [s.admit('a', 'nav_goal', {}).code for _ in range(4)]
    assert codes == ['', '', 'rate_limited', 'rate_limited']


def test_the_drivers_stop_is_never_rate_limited():
    """With every bucket empty, the driver's STOP still goes through."""
    s, _clock, _stops = make(command_rate=1.0, command_burst=1.0,
                             frame_rate=1.0, frame_burst=2.0)
    joined(s, 'a')
    claim(s, 'a')
    while s.admit('a', 'nav_goal', {}).ok:
        pass
    assert s.admit('a', 'ping', {}).code == 'rate_limited'
    for _ in range(20):
        assert s.admit('a', 'stop', {}).ok
        assert s.admit('a', 'set_mode', {'mode': 'stop'}).ok


def test_one_spectator_cannot_monopolise_the_server():
    """A flooding spectator is limited and closed; others are unaffected."""
    s, _clock, _stops = make(frame_rate=60.0, frame_burst=60.0,
                             abuse_limit=50)
    joined(s, 'flood', 'quiet', 'driver')
    claim(s, 'driver')
    verdicts = [s.admit('flood', 'ping', {}) for _ in range(200)]
    assert sum(v.ok for v in verdicts) == 60
    assert any(v.close for v in verdicts)
    assert s.admit('quiet', 'ping', {}).ok
    assert s.admit('driver', 'drive', {}).ok


def test_spectator_command_spam_is_limited_and_closed():
    """Refused commands are counted; sustained refusal closes the socket."""
    s, _clock, _stops = make(abuse_limit=10)
    joined(s, 'driver', 'w')
    claim(s, 'driver')
    verdicts = [s.admit('w', 'drive', {}) for _ in range(10)]
    assert not any(v.ok for v in verdicts)
    assert verdicts[-1].close and not verdicts[-2].close


def test_rate_limits_are_per_client():
    """One client's empty bucket does not empty another's."""
    s, _clock, _stops = make(frame_rate=5.0, frame_burst=5.0)
    joined(s, 'a', 'b')
    for _ in range(5):
        assert s.admit('a', 'ping', {}).ok
    assert s.admit('a', 'ping', {}).code == 'rate_limited'
    assert s.admit('b', 'ping', {}).ok


def test_token_bucket_refills_at_its_rate():
    """The bucket on its own: burst, then rate."""
    bucket = control.TokenBucket(rate=2.0, burst=2.0, now=0.0)
    assert [bucket.take(0.0) for _ in range(3)] == [True, True, False]
    assert bucket.take(0.5)
    assert not bucket.take(0.5)
    assert [bucket.take(10.0) for _ in range(3)] == [True, True, False]


# ── host kill ──────────────────────────────────────────────────────────

def test_kill_stops_ends_and_voids():
    """The host's kill switch: stop, session over, code void, no driver."""
    s, _clock, stops = make()
    joined(s, 'a', 'b')
    claim(s, 'a')
    s.kill()
    assert stops.reasons == [control.END_KILLED]
    assert s.over == control.END_KILLED
    assert s.driver is None and s.code is None


def test_nobody_regains_control_after_a_kill():
    """Not the old driver, not a spectator, not a new connection."""
    s, _clock, _stops = make()
    joined(s, 'a', 'b')
    claim(s, 'a')
    s.kill()
    for cid in ('a', 'b'):
        assert claim(s, cid).code == 'session_over'
        for kind in sorted(control.COMMAND_INTENTS):
            assert not s.admit(cid, kind, {}).ok
    assert not s.connect('c').ok
    assert s.driver is None


def test_kill_stops_even_with_no_driver_and_twice():
    """Killing an idle session still requests a stop, and again on repeat."""
    s, _clock, stops = make()
    s.kill()
    s.kill()
    assert stops.reasons == [control.END_KILLED, control.END_KILLED]


def test_kill_works_in_open_access_too():
    """The host's switch is not a code-mode feature: it ends open too."""
    s, _clock, stops = make(access=control.ACCESS_OPEN)
    assert s.admit('a', 'drive', {}).ok
    s.kill()
    assert stops.reasons == [control.END_KILLED]
    assert s.over == control.END_KILLED
    for kind in sorted(control.COMMAND_INTENTS):
        assert s.admit('a', kind, {}).code == 'session_over', kind
    assert s.admit('a', 'ping', {}).ok
    assert not s.connect('b').ok


# ── stop on every ending; fail closed ──────────────────────────────────

@pytest.mark.parametrize('end', ['release', 'idle', 'disconnect',
                                 'reconcile', 'expire', 'kill'])
def test_every_ending_requests_a_stop(end):
    """Whatever ends control or the session, on_stop is called once."""
    s, clock, stops = make(idle_s=60.0, cap_s=600.0)
    joined(s, 'a')
    claim(s, 'a')
    if end == 'release':
        s.admit('a', 'release', {})
    elif end == 'idle':
        clock.advance(60.0)
        s.tick()
    elif end == 'disconnect':
        s.disconnect('a')
    elif end == 'reconcile':
        s.reconcile([])
    elif end == 'expire':
        clock.advance(600.0)
        s.tick(busy=True)
    else:
        s.kill()
    assert len(stops.reasons) == 1, stops.reasons
    assert s.driver is None


def test_a_spectator_leaving_does_not_stop():
    """Only the driver's departure stops COCO."""
    s, _clock, stops = make()
    joined(s, 'a', 'b')
    claim(s, 'a')
    s.disconnect('b')
    assert stops.reasons == [] and s.driver == 'a'


def test_a_driver_missing_from_the_live_set_is_released():
    """Lost driver state fails closed: release and stop."""
    s, _clock, stops = make()
    joined(s, 'a', 'b')
    claim(s, 'a')
    s.reconcile(['b'])
    assert s.driver is None
    assert stops.reasons == [control.END_AMBIGUOUS]


def test_reconcile_with_the_driver_present_changes_nothing():
    """A consistent registry is left alone."""
    s, _clock, stops = make()
    joined(s, 'a', 'b')
    claim(s, 'a')
    s.reconcile(['a', 'b'])
    assert s.driver == 'a' and stops.reasons == []


def test_a_frame_from_an_unknown_connection_is_refused_and_closed():
    """A client this session never admitted cannot command anything."""
    s, _clock, _stops = make()
    joined(s, 'a')
    claim(s, 'a')
    verdict = s.admit('ghost', 'stop', {})
    assert not verdict.ok and verdict.close


def test_telemetry_never_carries_the_code():
    """The control block is safe to broadcast."""
    s, _clock, _stops = make()
    joined(s, 'a')
    claim(s, 'a')
    for cid in ('a', 'b', None):
        assert CODE not in repr(s.as_dict(cid))


def test_policy_rejects_nonsense():
    """A zero or negative limit is a configuration error, not a policy."""
    with pytest.raises(ValueError):
        control.Policy(idle_s=0)
    with pytest.raises(ValueError):
        control.Policy(max_clients=0)
    with pytest.raises(ValueError):
        control.ControlSession('code-ish', clock=FakeClock())
    with pytest.raises(ValueError):
        control.ControlSession(control.ACCESS_CODE)


# ── malformed frames ───────────────────────────────────────────────

def test_garbage_is_charged_and_closed():
    """Undecodable frames take frame tokens and count toward abuse."""
    s, _clock, _stops = make(frame_rate=10.0, frame_burst=10.0,
                             abuse_limit=5)
    joined(s, 'g')
    verdicts = [s.malformed('g') for _ in range(5)]
    assert verdicts[-1].close and not verdicts[-2].close
    s2, _c, _s = make(frame_rate=3.0, frame_burst=3.0)
    joined(s2, 'g')
    codes = [s2.malformed('g').code for _ in range(4)]
    assert codes[-1] == 'rate_limited'


def test_garbage_from_an_unknown_connection_closes():
    """Fail closed on a connection the session never admitted."""
    s, _clock, _stops = make()
    assert s.malformed('ghost').close


def test_open_access_never_charges_garbage():
    """Open access is P0.1: no limits."""
    s, _clock, _stops = make(access=control.ACCESS_OPEN)
    assert all(s.malformed('x').ok for _ in range(1000))


# ── telemetry block ────────────────────────────────────────────────────

def test_the_broadcast_block_names_the_driver_connection_only():
    """driver_id lets each client compare with its own welcome.you."""
    s, _clock, _stops = make()
    joined(s, 'a', 'b')
    assert s.as_dict()['driver_id'] is None
    claim(s, 'a')
    block = s.as_dict()
    assert block['driver'] is True and block['driver_id'] == 'a'
    assert 'role' not in block
    assert s.as_dict('b')['role'] == 'spectator'


def test_the_public_summary_has_no_ids_and_no_code():
    """/healthz may say a session is live; it may not say who drives."""
    s, _clock, _stops = make()
    joined(s, 'a')
    claim(s, 'a')
    summary = s.summary()
    assert summary['driver'] is True and summary['access'] == 'code'
    assert 'driver_id' not in summary and CODE not in repr(summary)
    assert "'a'" not in repr(summary)


# ── origins ────────────────────────────────────────────────────────────

PAGES = 'https://gauthamcodes.github.io'
ALLOWED = control.parse_origins(f'{PAGES}, http://localhost:*, '
                                'http://127.0.0.1:*,')


@pytest.mark.parametrize('origin', [
    PAGES, PAGES + '/', 'https://GauthamCodes.github.io',
    'http://localhost', 'http://localhost:4173', 'http://localhost:8080',
    'http://127.0.0.1:5173'])
def test_allowed_origins(origin):
    """The Pages site and localhost on any port."""
    assert control.origin_allowed(origin, ALLOWED)


@pytest.mark.parametrize('origin', [
    None, '', 'null', 'https://evil.example', 'http://gauthamcodes.github.io',
    'https://gauthamcodes.github.io.evil.example', 'https://localhost:4173',
    'http://localhost:4173.evil.example', 'http://localhost:', 'http://localhost:80a',
    'http://localhost.evil.example', 'https://other.github.io'])
def test_refused_origins(origin):
    """Anything else, including look-alikes and the wrong scheme."""
    assert not control.origin_allowed(origin, ALLOWED)


def test_no_origin_list_is_any_origin():
    """Empty keeps P0.1's local behaviour."""
    assert control.origin_allowed('https://evil.example', ())
    assert control.parse_origins('') == ()
    assert control.parse_origins(None) == ()
    assert control.parse_origins(' * ') == ()


# ── purity ─────────────────────────────────────────────────────────────

def test_control_is_pure():
    """No rclpy, no tornado, no sockets, no sleeping: policy only."""
    source = pathlib.Path(control.__file__).read_text()
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split('.')[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or '').split('.')[0])
    # No `time` either: the clock is injected, so nothing here can sleep.
    assert imported <= {'dataclasses', 'hmac', 'secrets', 'threading'}
