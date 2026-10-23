// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
export const PREFERENCES_CHANGED = 'coco-preferences-changed';
export const SETTINGS_OPEN = 'coco-settings-open';
export const openSettings = () => window.dispatchEvent(new Event(SETTINGS_OPEN));
export const notifySettings = () => window.dispatchEvent(new Event(PREFERENCES_CHANGED));
