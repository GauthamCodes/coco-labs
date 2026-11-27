// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R5.6: a Python error from the worker, in words. A traceback's last line is the exception and its own
 * message (e.g. the World Spec reader's refusal, which names its reason); the frames above it are for
 * developers (logged to the console, not shown). Anything that is not a traceback is returned as it is.
 */
export function pyReason(message: string): string {
  if (!/Traceback \(most recent call last\)/.test(message)) return message;
  const lines = message.split('\n').map((l) => l.trim()).filter(Boolean);
  const last = lines[lines.length - 1] ?? message;
  return last.replace(/^[A-Za-z_.]*?(\w+(Error|Exception)): /, '$1: ');
}
