// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.4: a message as `ros2 topic echo` prints it -- YAML, nested keys, `- ` list items, numbers
 * in full (a float32 range prints its float32 value) -- with long arrays cut to their first
 * `maxItems` values and a count, so a 480-beam scan or a 161,700-cell map stays readable.
 */

function scalar(v: unknown): string {
  if (typeof v === 'number') {
    if (Number.isNaN(v)) return '.nan';
    if (v === Infinity) return '.inf';
    if (v === -Infinity) return '-.inf';
    return Object.is(v, -0) ? '-0.0' : String(v);
  }
  if (typeof v === 'string') return v === '' ? "''" : /[:#\-\[\]{},&*!|>'"%@`]|^\s|\s$/.test(v) ? `'${v.replace(/'/g, "''")}'` : v;
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  return 'null';
}

export function toYaml(msg: unknown, maxItems = 8, indent = ''): string {
  const out: string[] = [];
  const walk = (v: unknown, pad: string) => {
    if (Array.isArray(v)) {
      if (!v.length) { out[out.length - 1] += ' []'; return; }
      v.slice(0, maxItems).forEach((x) => {
        if (x && typeof x === 'object' && !Array.isArray(x)) {
          const lines = toYaml(x, maxItems, pad + '  ').split('\n');
          out.push(`${pad}- ${lines[0].trimStart()}`, ...lines.slice(1));
        } else out.push(`${pad}- ${scalar(x)}`);
      });
      if (v.length > maxItems) out.push(`${pad}- '... ${v.length - maxItems} more (${v.length} values)'`);
      return;
    }
    for (const [k, x] of Object.entries(v as Record<string, unknown>)) {
      if (x && typeof x === 'object') { out.push(`${pad}${k}:`); walk(x, Array.isArray(x) ? pad : pad + '  '); }
      else out.push(`${pad}${k}: ${scalar(x)}`);
    }
  };
  walk(msg, indent);
  return out.join('\n');
}
