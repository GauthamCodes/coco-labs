/* Copyright 2026 Gautham Anil
 * SPDX-License-Identifier: Apache-2.0
 *
 * Reference outputs for coco_lab.rng, from the published algorithms:
 * SplitMix64 and xoshiro256** 1.0 (David Blackman and Sebastiano Vigna,
 * https://prng.di.unimi.it/, public domain), transcribed unchanged. The
 * printed numbers are committed as coco_lab/test/rng_vectors.json; coco_lab's
 * test checks the Python generator against them.
 *
 *   cc -O2 -o xr xoshiro_reference.c && ./xr > ../../../../../coco_lab/test/rng_vectors.json
 */
#include <stdint.h>
#include <stdio.h>

static uint64_t sm_state;
static uint64_t splitmix64(void) {
  uint64_t z = (sm_state += 0x9e3779b97f4a7c15);
  z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9;
  z = (z ^ (z >> 27)) * 0x94d049bb133111eb;
  return z ^ (z >> 31);
}

static inline uint64_t rotl(const uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }
static uint64_t s[4];
static uint64_t next(void) {
  const uint64_t result = rotl(s[1] * 5, 7) * 9;
  const uint64_t t = s[1] << 17;
  s[2] ^= s[0];
  s[3] ^= s[1];
  s[1] ^= s[2];
  s[0] ^= s[3];
  s[2] ^= t;
  s[3] = rotl(s[3], 45);
  return result;
}

int main(void) {
  const uint64_t seeds[] = {0ULL, 1ULL, 42ULL, 20261008ULL, 0xFFFFFFFFFFFFFFFFULL};
  printf("{\"algorithm\": \"xoshiro256** seeded by SplitMix64\",\n \"cases\": [\n");
  for (int c = 0; c < 5; c++) {
    sm_state = seeds[c];
    for (int i = 0; i < 4; i++) s[i] = splitmix64();
    printf("  {\"seed\": \"%llu\", \"first\": [", (unsigned long long)seeds[c]);
    for (int i = 0; i < 8; i++) printf("%s\"%llu\"", i ? ", " : "", (unsigned long long)next());
    printf("]}%s\n", c < 4 ? "," : "");
  }
  printf(" ]}\n");
  return 0;
}
