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
Who may control COCO: one driver holding a code, everyone else watching.

Pure module: no rclpy, no sockets, no wall clock. The clock is injected and
stopping the robot is an injected callback, so every rule below is proved by
unit tests that never sleep (``test/test_control.py``).

Two access modes
----------------
``open`` (the default, local) is P0.1's behaviour exactly: anyone connected
may command COCO, the node's pilot lock decides who holds the stick, and
anyone may press STOP. ``ControlSession`` in this mode admits every frame
and changes nothing.

``code`` is for a remote session (Phase 2 Part C, docs/live/PART_C_REPORT.md):

- The HOST generates a control code per session (``new_code``). It is
  printed on the host and returned by the host-only service; it never
  rides a URL (Tailscale #18651 strips WebSocket query strings, and URLs
  end up in logs). It rides inside a ``claim`` frame.
- ``claim {code}`` makes that client THE driver. There is exactly one. A
  second claim while a driver holds control is refused (``driver_present``),
  whoever sends it and whatever code it carries: control is never
  transferred implicitly, only after the holder lets go (``release``, idle
  timeout, disconnect) and someone claims again.
- Every command intent (``COMMAND_INTENTS``) from anyone but the driver is
  refused ``spectator``. That includes STOP: owner decision 3 (2026-10-02,
  docs/live/SAFETY_FIXES.md) is that spectators get no STOP, because on
  the public internet a STOP for every viewer is a grief button. The host
  stops the robot with the kill switch.
- Spectators keep telemetry, the map, the camera and the lidar: the
  read-only intents (``hello``, ``ping``, ``subscribe`` and friends).

Endings, and the one rule they share
------------------------------------
Every way control ends calls ``on_stop(reason)``: an explicit ``release``,
the idle timeout, the driver disconnecting, ownership found inconsistent
(``reconcile``), the session cap, and the host's kill switch. The platform
wires ``on_stop`` to its latched STOP, which zeroes the wheels, aborts a
running mission and holds the arbiter idle. Releasing control therefore
never leaves the robot moving on the last command of someone who is no
longer driving.

The session cap and the kill switch also END the session: the code is
invalidated, the driver cleared, and every later claim or command is
refused ``session_over`` until the host creates a new session (a new
``ControlSession``, with a new code).

Idle, and autonomy
------------------
The idle clock is reset by the driver's command intents. A fetch runs for
minutes with nobody touching anything, so ``tick(busy=True)`` -- the
platform passes "the executive reports a mission running, or a Nav2 goal
the browser sent is active" -- also counts as activity. A stale or unknown
mission state is NOT busy, so the idle clock runs (fail closed). The
session cap bounds everything regardless.

Rate limits
-----------
Token buckets per client, in code mode only:

- every frame, read-only ones included: ``frame_rate`` per second, so no
  single spectator can monopolise the server's loop;
- ``drive``: ``drive_rate`` per second (the page sends 10 Hz);
- every other command intent, ``claim`` included: ``command_rate``.

A refused frame is answered ``rate_limited``. A client refused
``abuse_limit`` times in a row, or that presents ``bad_code_limit`` wrong
codes, is told to close (``Verdict.close``).
"""

from dataclasses import dataclass
import hmac
import secrets
import threading

ACCESS_OPEN = 'open'
ACCESS_CODE = 'code'
ACCESS_MODES = (ACCESS_OPEN, ACCESS_CODE)

#: Intents that command the robot. Only the driver may send them in code
#: mode. ``stop`` is one of them by owner decision 3.
COMMAND_INTENTS = frozenset({
    'drive', 'stop', 'set_mode', 'select_target', 'mission', 'nav_goal',
    'set_arm', 'set_gripper',
})

#: Intents that change only what this client is SENT. Allowed to anyone.
READ_INTENTS = frozenset({
    'hello', 'ping', 'subscribe', 'unsubscribe', 'set_stream',
})

#: The two intents this module adds to coco.v1 (additive).
CONTROL_INTENTS = frozenset({'claim', 'release'})

#: Refusal codes this module can return, with the text a UI may show.
#: Added to ``protocol.REFUSAL_CODES`` (additive).
REFUSALS = {
    'spectator': 'you are watching this session; only the driver who '
                 'entered the control code can command COCO',
    'bad_code': 'that control code is not valid for this session',
    'driver_present': 'someone else holds control; it is released only '
                      'when they let go or go idle',
    'rate_limited': 'too many frames; slow down',
    'session_over': 'this live session has ended; COCO is stopped',
    'session_full': 'this live session is full; try again later',
    'open_access': 'this session is open: no control code is needed',
}

#: Why control ended; passed to ``on_stop`` and shown in telemetry.
END_RELEASED = 'released'
END_IDLE = 'idle_timeout'
END_DISCONNECT = 'driver_disconnected'
END_AMBIGUOUS = 'ownership_lost'
END_EXPIRED = 'expired'
END_KILLED = 'killed'

#: Unambiguous characters only (no 0/O, 1/I/L), so a code read aloud or
#: typed on a phone survives. 31 symbols, 8 of them: ~39.6 bits.
CODE_ALPHABET = '23456789ABCDEFGHJKMNPQRSTUVWXYZ'
CODE_LENGTH = 8


def new_code(rng=None):
    """Generate a control code from a CSPRNG (``secrets``) by default."""
    choice = rng.choice if rng is not None else secrets.choice
    return ''.join(choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def is_stop(kind, frame):
    """Whether this intent is a STOP: ``stop``, or the Stop mode button."""
    return kind == 'stop' or (kind == 'set_mode'
                              and (frame or {}).get('mode') == 'stop')


def normalise_code(code):
    """Uppercase and drop spaces and dashes; None for a non-string."""
    if not isinstance(code, str):
        return None
    return code.replace(' ', '').replace('-', '').upper()[:64]


@dataclass(frozen=True)
class Policy:
    """The numbers. Defaults are Part A §5.3's proposals, not measurements."""

    idle_s: float = 60.0
    cap_s: float = 1200.0
    max_clients: int = 25
    frame_rate: float = 60.0
    frame_burst: float = 60.0
    drive_rate: float = 20.0
    drive_burst: float = 20.0
    command_rate: float = 2.0
    command_burst: float = 6.0
    bad_code_limit: int = 5
    abuse_limit: int = 100

    def __post_init__(self):
        """Refuse a policy that could not work, rather than run it."""
        for name in ('idle_s', 'cap_s', 'frame_rate', 'frame_burst',
                     'drive_rate', 'drive_burst', 'command_rate',
                     'command_burst'):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not value > 0:
                raise ValueError(f'{name} must be > 0, got {value!r}')
        for name in ('max_clients', 'bad_code_limit', 'abuse_limit'):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 1:
                raise ValueError(f'{name} must be an int >= 1, got {value!r}')


@dataclass(frozen=True)
class Verdict:
    """What to do with one frame: act on it, or refuse with a code."""

    ok: bool
    code: str = ''
    close: bool = False


ALLOW = Verdict(True)


class TokenBucket:
    """A token bucket on the injected clock. Not thread-safe on its own."""

    def __init__(self, rate, burst, now):
        """Start full."""
        self.rate = float(rate)
        self.burst = float(burst)
        self.tokens = float(burst)
        self.at = now

    def take(self, now):
        """Take one token if there is one."""
        if now > self.at:
            self.tokens = min(self.burst,
                              self.tokens + (now - self.at) * self.rate)
            self.at = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class _Client:
    """Per-client bookkeeping: buckets and refusal counts."""

    def __init__(self, policy, now):
        self.frames = TokenBucket(policy.frame_rate, policy.frame_burst, now)
        self.drives = TokenBucket(policy.drive_rate, policy.drive_burst, now)
        self.commands = TokenBucket(policy.command_rate,
                                    policy.command_burst, now)
        self.bad_codes = 0
        self.refused_in_row = 0


class ControlSession:
    """
    One live session's control policy. Thread-safe.

    ``clock`` is a monotonic seconds source, ``on_stop(reason)`` stops the
    robot. In ``open`` access the session admits everything and neither is
    ever used for control.
    """

    def __init__(self, access=ACCESS_OPEN, policy=None, clock=None,
                 on_stop=None, code=None):
        """Create the session; in code mode, with a fresh code by default."""
        if access not in ACCESS_MODES:
            raise ValueError(f'access must be one of {ACCESS_MODES}, '
                             f'got {access!r}')
        if clock is None:
            raise ValueError('a clock is required (inject time.monotonic)')
        self.access = access
        self.policy = policy or Policy()
        self._clock = clock
        self._on_stop = on_stop or (lambda reason: None)
        self._lock = threading.RLock()
        self._started = clock()
        self._code = None
        if access == ACCESS_CODE:
            self._code = normalise_code(code) if code else new_code()
            if not self._code:
                raise ValueError('an explicit code must be a non-empty string')
        self._driver = None
        self._driver_since = None
        self._last_active = None
        self._clients = {}
        self._over = None
        self._last_end = None
        self._stops = 0

    # ── what the host and telemetry may read ───────────────────────────
    @property
    def code(self):
        """Return the control code, for the HOST only; None once ended."""
        with self._lock:
            return self._code

    @property
    def driver(self):
        """Return the driver's client id, or None."""
        with self._lock:
            return self._driver

    @property
    def over(self):
        """Why the session ended (expired, killed), or None while live."""
        with self._lock:
            return self._over

    @property
    def code_mode(self):
        """Whether this session enforces driver and spectators."""
        return self.access == ACCESS_CODE

    def ends_at(self):
        """When the session cap ends it, on the injected clock."""
        return self._started + self.policy.cap_s

    # ── connections ────────────────────────────────────────────────────
    def connect(self, client_id):
        """
        Admit a new connection, or refuse it.

        Refused when the session is over or full. Open access admits
        everyone, exactly as before.
        """
        with self._lock:
            if not self.code_mode:
                return ALLOW
            self._expire_if_due()
            if self._over:
                return Verdict(False, 'session_over', close=True)
            if (client_id not in self._clients
                    and len(self._clients) >= self.policy.max_clients):
                return Verdict(False, 'session_full', close=True)
            self._clients.setdefault(client_id, _Client(self.policy,
                                                        self._clock()))
            return ALLOW

    def disconnect(self, client_id):
        """Forget a connection; the driver leaving stops the robot."""
        with self._lock:
            self._clients.pop(client_id, None)
            if self._driver is not None and self._driver == client_id:
                self._end_control(END_DISCONNECT)

    def reconcile(self, connected_ids):
        """
        Fail closed on inconsistent ownership.

        If the recorded driver is not among the live connections -- a lost
        close event, a handler that died -- control is released and the
        robot stopped, rather than held by nobody in particular.
        """
        with self._lock:
            live = set(connected_ids)
            for gone in set(self._clients) - live:
                self._clients.pop(gone, None)
            if self._driver is not None and self._driver not in live:
                self._end_control(END_AMBIGUOUS)

    # ── frames ─────────────────────────────────────────────────────────
    def admit(self, client_id, kind, frame=None):
        """
        Decide one validated frame from ``client_id``.

        ``claim`` and ``release`` are acted on here; for every other kind
        the caller acts only when the verdict is ok.
        """
        frame = frame or {}
        with self._lock:
            if not self.code_mode:
                if kind in CONTROL_INTENTS:
                    return Verdict(False, 'open_access')
                return ALLOW
            now = self._clock()
            self._expire_if_due(now)
            client = self._clients.get(client_id)
            if client is None:
                # A frame from a connection this session never admitted:
                # an ownership ambiguity, so it is refused.
                return Verdict(False, 'session_over' if self._over
                               else 'spectator', close=True)
            if (is_stop(kind, frame) and not self._over
                    and self._driver is not None
                    and self._driver == client_id):
                # The driver's STOP is never rate-limited: honouring one
                # more STOP is always safe, refusing one never is.
                self._last_active = now
                client.refused_in_row = 0
                return ALLOW
            if not client.frames.take(now):
                return self._refuse(client, 'rate_limited')
            if kind in READ_INTENTS:
                client.refused_in_row = 0
                return ALLOW
            if self._over:
                return self._refuse(client, 'session_over')
            bucket = client.drives if kind == 'drive' else client.commands
            if not bucket.take(now):
                return self._refuse(client, 'rate_limited')
            if kind == 'claim':
                return self._claim(client_id, client, frame.get('code'), now)
            if kind == 'release':
                if self._driver != client_id:
                    return self._refuse(client, 'spectator')
                self._end_control(END_RELEASED)
                client.refused_in_row = 0
                return ALLOW
            if kind in COMMAND_INTENTS:
                if self._driver is None or self._driver != client_id:
                    return self._refuse(client, 'spectator')
                self._last_active = now
                client.refused_in_row = 0
                return ALLOW
            # An intent this module was never told about is refused, not
            # waved through: the safe default for a new command type.
            return self._refuse(client, 'spectator')

    def _claim(self, client_id, client, code, now):
        if self._driver is not None:
            if self._driver == client_id:
                self._last_active = now
                client.refused_in_row = 0
                return ALLOW
            return self._refuse(client, 'driver_present')
        given = normalise_code(code)
        if not given or not hmac.compare_digest(
                given.encode(), (self._code or '').encode()):
            client.bad_codes += 1
            verdict = self._refuse(client, 'bad_code')
            if client.bad_codes >= self.policy.bad_code_limit:
                return Verdict(False, 'bad_code', close=True)
            return verdict
        self._driver = client_id
        self._driver_since = now
        self._last_active = now
        client.bad_codes = 0
        client.refused_in_row = 0
        return ALLOW

    def _refuse(self, client, code):
        client.refused_in_row += 1
        return Verdict(False, code,
                       close=client.refused_in_row >= self.policy.abuse_limit)

    # ── time ───────────────────────────────────────────────────────────
    def tick(self, busy=False):
        """
        Apply the session cap and the idle timeout on the injected clock.

        ``busy`` is True while autonomy the driver started is running
        (see the module docstring); it counts as the driver's activity.
        Returns the ending applied this tick, or None.
        """
        with self._lock:
            if not self.code_mode:
                return None
            now = self._clock()
            if self._expire_if_due(now):
                return END_EXPIRED
            if self._driver is None:
                return None
            if busy is True:
                self._last_active = now
                return None
            if now - self._last_active >= self.policy.idle_s:
                self._end_control(END_IDLE)
                return END_IDLE
            return None

    def _expire_if_due(self, now=None):
        if self._over or not self.code_mode:
            return False
        now = self._clock() if now is None else now
        if now - self._started < self.policy.cap_s:
            return False
        self._end_session(END_EXPIRED)
        return True

    # ── host ───────────────────────────────────────────────────────────
    def kill(self):
        """
        Kill the session: the host's switch. Stop, end, void the code.

        Works in either access mode, and twice is harmless (it stops
        again). Nothing a client sends can undo it; only a new session.
        """
        with self._lock:
            self._end_session(END_KILLED)

    # ── endings ────────────────────────────────────────────────────────
    def _end_control(self, reason):
        self._driver = None
        self._driver_since = None
        self._last_active = None
        self._last_end = reason
        self._stop(reason)

    def _end_session(self, reason):
        self._over = reason
        self._code = None
        self._driver = None
        self._driver_since = None
        self._last_active = None
        self._last_end = reason
        self._stop(reason)

    def _stop(self, reason):
        self._stops += 1
        # Called under the lock, deliberately: a second ending cannot
        # interleave with this one. on_stop must not call back in.
        self._on_stop(reason)

    # ── telemetry ──────────────────────────────────────────────────────
    def as_dict(self, client_id=None):
        """
        Build the ``platform.control`` block (additive), for one client.

        Never contains the code. ``role`` is this client's: driver,
        spectator, or open (anyone may command).
        """
        with self._lock:
            now = self._clock()
            if not self.code_mode:
                return {'access': self.access, 'role': 'open'}
            idle_left = None
            if self._driver is not None and self._last_active is not None:
                idle_left = max(0.0, self.policy.idle_s
                                - (now - self._last_active))
            return {
                'access': self.access,
                'role': ('driver' if client_id is not None
                         and client_id == self._driver else 'spectator'),
                'driver': self._driver is not None,
                'clients': len(self._clients),
                'max_clients': self.policy.max_clients,
                'idle_s': self.policy.idle_s,
                'idle_left_s': idle_left,
                'session_left_s': (0.0 if self._over else max(
                    0.0, self.ends_at() - now)),
                'over': self._over,
                'last_end': self._last_end,
            }
