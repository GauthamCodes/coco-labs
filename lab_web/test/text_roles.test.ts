// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { expect, it } from 'vitest';
import { TOKENS } from '../src/ui/tokens';
import { contrast } from '../src/ui/colour_checks';
it('evidence text stays AA in each theme independently of OS colour scheme',()=>{for(const p of Object.values(TOKENS.colours))for(const role of ['badgeModel','badgeStack','labelSuccess','labelWarning','labelError'] as const)for(const background of ['bg','panel','panel2'] as const)expect(contrast(p[role],p[background])).toBeGreaterThanOrEqual(4.5)});
