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

r"""
The Arena's random numbers: specified, in-library, bit-exact everywhere.

``random.Random`` is deterministic only within CPython's own Mersenne
Twister; a second implementation (a TypeScript or WebAssembly port, which
README section 3 allows if it is trace-equivalent) would have to reproduce
it exactly. This generator is small enough to reproduce from its
definition:

- **xoshiro256\*\*** (Blackman and Vigna, 2018) for the 64-bit stream;
- seeded by **SplitMix64** from one 64-bit seed (the authors' recommended
  seeding), so seed 0 is valid;
- ``random()`` = the top 53 bits / 2**53, a double in [0, 1);
- ``gauss()`` = Box-Muller from two ``random()`` draws (the second value
  is discarded, so every call consumes exactly two draws and a state
  layout never depends on call parity);
- ``split()`` = a new independent stream seeded from this one's next draw.

Integer arithmetic only, masked to 64 bits; the state is four 64-bit words
(:attr:`Rng.state`), which the Arena's per-tick state hash includes.
Test vectors pin the first outputs (``test/test_rng.py``).
"""

import math
from typing import Tuple

MASK = (1 << 64) - 1


def splitmix64(x: int) -> Tuple[int, int]:
    """Return ``(output, next_state)`` of SplitMix64 from state ``x``."""
    x = (x + 0x9E3779B97F4A7C15) & MASK
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return z ^ (z >> 31), x


def _rotl(x: int, k: int) -> int:
    return ((x << k) | (x >> (64 - k))) & MASK


class Rng:
    """xoshiro256** seeded by SplitMix64."""

    def __init__(self, seed: int):
        """Seed from a 64-bit integer (0 included)."""
        if isinstance(seed, bool) or not isinstance(seed, int) \
                or not 0 <= seed <= MASK:
            raise ValueError(f'seed must be an int in [0, 2**64), got {seed!r}')
        s, x = [], seed
        for _ in range(4):
            out, x = splitmix64(x)
            s.append(out)
        self.state = s

    def next_u64(self) -> int:
        """Return the next 64-bit output."""
        s = self.state
        result = (_rotl((s[1] * 5) & MASK, 7) * 9) & MASK
        t = (s[1] << 17) & MASK
        s[2] ^= s[0]
        s[3] ^= s[1]
        s[1] ^= s[2]
        s[0] ^= s[3]
        s[2] ^= t
        s[3] = _rotl(s[3], 45)
        return result

    def random(self) -> float:
        """Return a float in [0, 1) from the top 53 bits."""
        return (self.next_u64() >> 11) * (1.0 / (1 << 53))

    def gauss(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        """Return a normal deviate (Box-Muller; always two draws)."""
        u1 = self.random()
        u2 = self.random()
        r = math.sqrt(-2.0 * math.log(1.0 - u1))
        return mu + sigma * r * math.cos(2.0 * math.pi * u2)

    def split(self) -> 'Rng':
        """Return an independent stream seeded from the next output."""
        return Rng(self.next_u64())
