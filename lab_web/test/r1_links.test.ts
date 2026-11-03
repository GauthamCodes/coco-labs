// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** R1.4: experiment links round-trip, stay bounded and refuse what is not a spec. */
import { describe, expect, it } from 'vitest';
import { experimentLink, readExperimentLink, SHORT_LINK } from '../src/workbench/links';
import { defaultSpec, type ExperimentSpec } from '../src/workbench/spec';

const open = (url: string) => { const u = new URL(url); return readExperimentLink(u.search, u.hash); };

describe('experiment links', () => {
  it('a short spec travels in ?exp= and comes back identical, digest included', () => {
    const spec = defaultSpec('planning');
    const url = experimentLink(spec, 'https://x.test/coco-labs/', 'a'.repeat(64));
    expect(url.length).toBeLessThanOrEqual(SHORT_LINK);
    expect(url).toContain('?view=workbench&exp=');
    expect(open(url)).toEqual({ spec, digest: 'a'.repeat(64) });
  });

  it('a long spec is deflated into the fragment and comes back identical', () => {
    const spec: ExperimentSpec = { ...defaultSpec('planning'), scenarios: { kind: 'pairs', pairs: [...Array(80).keys()].map((i) => ({ start: [1 + i / 10, 2, 0.5], goal: [10, 2 + i / 7] })) } };
    const url = experimentLink(spec, 'https://x.test/coco-labs/');
    expect(url).toContain('#expz=');
    expect(new URL(url).search).toBe('?view=workbench');
    expect(open(url)).toEqual({ spec, digest: null });
  });

  it('refuses a malformed payload, a wrong schema and a bad digest; no payload is not a link', () => {
    expect(() => open('https://x.test/?view=workbench&exp=!!')).toThrow();
    const notSpec = btoa(JSON.stringify({ schema: 'other' })).replace(/=+$/, '');
    expect(() => open(`https://x.test/?view=workbench&exp=${notSpec}`)).toThrow(/coco.experiment.v1/);
    const ok = experimentLink(defaultSpec('control'), 'https://x.test/');
    expect(() => open(`${ok}&d=xyz`)).toThrow(/digest/);
    expect(open('https://x.test/?view=workbench')).toBeNull();
  });
});
