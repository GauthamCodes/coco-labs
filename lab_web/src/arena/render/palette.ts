// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { TOKENS } from '../../ui/tokens';
import { activeTheme } from '../../ui/theme';
export type { Palette, Theme } from '../../ui/tokens';
/** Fixed computation meanings, shared with every CSS/3D view. */
export const PALETTES = TOKENS.computation;
export const VIRIDIS = TOKENS.viridis;
export const currentTheme = activeTheme;
