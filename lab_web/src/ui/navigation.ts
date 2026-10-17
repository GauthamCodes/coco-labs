// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Same-document mode changes retain the warm interpreter and browser history. */
export function navigate(href: string): void {
  window.history.pushState(null, '', href);
  window.dispatchEvent(new PopStateEvent('popstate'));
  window.scrollTo(0, 0);
}
