// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** CSS-pixel rectangles in WebGL's bottom-left coordinate convention. */
export function paneLayout(count: 1 | 2 | 4, width: number, height: number) {
  const columns = count === 1 || width < height ? 1 : 2;
  const rows = count / columns;
  return Array.from({ length: count }, (_, index) => ({
    left: index % columns * width / columns,
    bottom: (rows - 1 - Math.floor(index / columns)) * height / rows,
    width: width / columns,
    height: height / rows,
  }));
}
