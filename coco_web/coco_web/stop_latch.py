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
The latched STOP: once pressed, nothing moves until a mode is picked again.

Pure module, no rclpy, so the policy is proved without a ROS graph, like
``safety.py`` and the arbiter's ``select_source``.

Why it exists (Phase 2 Part A, measured, docs/live/PART_A_AUDIT.md)
------------------------------------------------------------------
STOP used to publish ONE zero on ``/cmd_vel_teleop``. The arbiter honours
teleop for 0.3 s, and then forwards whatever ``/mission/mode`` selects.
Pressed during a fetch, the wheels reached zero in 1.5 ms. Then the
executive re-asserted ``nav``, and the wheels were moving again at 723 ms:
152 moving commands over 7.7 s, until the mission was aborted by hand.

The owner's ruling (2026-10-02) is that STOP aborts a running mission,
puts the arbiter in ``idle``, and keeps it there until the user explicitly
picks a mode again. Nothing, the executive included, may re-assert a
moving mode after a STOP.

How that is enforced, in layers
-------------------------------
1. The executive asserts its mode only while a mission runs, and hands
   back ``idle`` once when it ends (mission_executive._assert_outputs).
   So after the abort, nothing re-asserts in normal operation.
2. STOP holds zeros on ``/cmd_vel_teleop`` for ``HOLD_S``. Teleop outranks
   every mode in the arbiter, so the wheels stay at zero while the abort
   is in flight, however the executive's 2 Hz timer interleaves with it.
3. While latched, a moving mode seen on ``/mission/mode`` is a violation.
   The server answers with ``idle`` and renews the zero hold, and counts
   it. In normal operation this never fires; it is the backstop.
4. While latched, the server refuses ``drive`` and ``nav_goal`` with
   ``stopped``. Picking a mode (``teleop``, ``auto``) or starting a
   mission is the explicit act that releases the latch.
"""

import threading

#: How long STOP holds explicit zeros on the teleop input. Long enough to
#: cover an abort's round trip and the executive's next 2 Hz assertion
#: (0.5 s); short enough not to stand in the way of a user who picks
#: teleop straight afterwards (releasing the latch cancels the hold).
HOLD_S = 1.0

#: Arbiter modes that let a source other than teleop drive the wheels,
#: in every spelling cmd_vel_arbiter.normalise_mode accepts.
MOVING_MODES = frozenset({
    'nav', 'auto', 'autonomous', 'nav2', 'rl', 'ramp', 'approach',
})

#: Mission states in which the executive is NOT running a mission. An
#: abort sent in any of these would be wrong: in IDLE it drives the
#: executive straight to ABORT, which is terminal ("restart the node for
#: another run"), so a STOP pressed while driving by hand would quietly
#: end autonomous mode for the rest of the session.
NOT_RUNNING = frozenset({'', 'IDLE', 'COMPLETE', 'ABORT'})

#: UI modes whose selection is the explicit act that releases the latch.
RELEASING_MODES = frozenset({'teleop', 'auto'})

#: Intents refused while latched, because each would start motion.
BLOCKED_INTENTS = frozenset({'drive', 'nav_goal'})


def is_moving_mode(mode):
    """Whether a ``/mission/mode`` value lets an autonomous source drive."""
    if not isinstance(mode, str):
        return False
    return mode.strip().lower() in MOVING_MODES


def mission_running(state, fresh):
    """
    Whether the executive is running a mission, from its own status line.

    ``state`` is the ``state=`` field of ``/mission/state`` and ``fresh``
    whether that line is recent. A stale or absent line is NOT running:
    the abort is only ever sent to an executive known to be mid-mission,
    and the zero hold and the idle mode stop the wheels either way.
    """
    if not fresh or not isinstance(state, str):
        return False
    return state.strip().upper() not in NOT_RUNNING


class StopLatch:
    """
    The latch itself: engaged by STOP, released by an explicit choice.

    Thread-safe. The tornado thread engages and releases it, and the
    rclpy thread checks it when a ``/mission/mode`` message arrives.
    """

    def __init__(self):
        """Start released: a fresh server has had no STOP pressed."""
        self._lock = threading.Lock()
        self._latched = False
        self._since = None
        self._violations = 0

    @property
    def latched(self):
        """Whether a STOP is in force."""
        with self._lock:
            return self._latched

    def engage(self, wall_now):
        """Latch. Pressing STOP again keeps the original time."""
        with self._lock:
            if not self._latched:
                self._since = wall_now
            self._latched = True

    def release(self):
        """Release; returns True if it had been latched."""
        with self._lock:
            was = self._latched
            self._latched = False
            self._since = None
            return was

    def releases(self, kind, frame):
        """Whether this validated intent is an explicit choice to move again."""
        if kind == 'set_mode':
            return frame.get('mode') in RELEASING_MODES
        if kind == 'mission':
            return frame.get('action') == 'start'
        return False

    def blocks(self, kind, frame=None):
        """
        Whether this intent must be refused because STOP is in force.

        A zero ``drive`` is never refused: it cannot start motion, and the
        page sends three of them after every STOP on purpose.
        """
        if not self.latched or kind not in BLOCKED_INTENTS:
            return False
        if kind == 'drive' and frame is not None and (
                frame.get('linear') == 0.0 and frame.get('angular') == 0.0):
            return False
        return True

    def violated_by(self, mode):
        """
        Record and report a moving mode seen while latched.

        Returns True when the caller must put the arbiter back in idle and
        renew the zero hold.
        """
        if not is_moving_mode(mode):
            return False
        with self._lock:
            if not self._latched:
                return False
            self._violations += 1
            return True

    def as_dict(self):
        """Return the telemetry block, additive: ``platform.stop``."""
        with self._lock:
            return {'latched': self._latched, 'since': self._since,
                    'violations': self._violations}


class ZeroHold:
    """
    Until when explicit zeros must be published. Pure: the caller's clock.

    The node's 10 Hz watchdog asks ``active(now)`` and publishes a zero
    while it is true.
    """

    def __init__(self):
        """No hold."""
        self._lock = threading.Lock()
        self._until = 0.0

    def hold(self, now, seconds=HOLD_S):
        """Hold zeros until ``now + seconds``, never shortening a hold."""
        with self._lock:
            self._until = max(self._until, now + seconds)

    def cancel(self):
        """End the hold now: the user picked a mode and may drive."""
        with self._lock:
            self._until = 0.0

    def active(self, now):
        """Whether a zero is due at ``now``."""
        with self._lock:
            return now < self._until
