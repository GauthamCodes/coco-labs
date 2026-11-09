#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.7: refuse a number typed into the paper's prose (every number comes from a macro).

    python docs/paper/scripts/lint_tex.py

Reads main.tex and sections/*.tex; removes comments, \\cite/\\ref/\\label/\\input arguments,
\\texttt{...} (names such as depot-long-50), \\begin/\\end arguments and the names "ROS~2", "ROS 2", "Nav2", "IEEE 754" and macro arguments (#1); any digit left is an error. Also refuses a macro used in the text that
generated/numbers.tex (or generated/results.tex) does not define.
"""
from pathlib import Path
import re
import sys

PAPER = Path(__file__).resolve().parents[1]
STRIP = [
    (re.compile(r'(?<!\\)%.*'), ''),
    (re.compile(r'\\(cite|cref|Cref|ref|label|input|includegraphics|bibliography|'
                r'bibliographystyle|documentclass|usepackage|IfFileExists|begin|end|'
                r'setlength|texttt|url|href)\*?(\[[^\]]*\])?\{[^{}]*\}'), ' '),
    (re.compile(r'ROS(~| )2'), 'ROS'),
    (re.compile(r'Nav2'), 'Nav'),
    (re.compile(r'Apache-2\.0'), 'Apache'),
    (re.compile(r'Smac 2D'), 'Smac'),
    (re.compile(r'IEEE(~| )754'), 'IEEE'),
    (re.compile(r'#\d'), ''),
    (re.compile(r'^\\newcommand.*'), ''),
    (re.compile(r'v[01]\b'), 'vN'),
]
DEFINED = re.compile(r'\\newcommand\{\\([A-Za-z]+)\}')
USED = re.compile(r'\\([A-Z][A-Za-z]+)\{\}')


def main():
    files = [PAPER / 'main.tex'] + sorted((PAPER / 'sections').glob('*.tex'))
    defined = set()
    for g in ('generated/numbers.tex', 'generated/results.tex'):
        p = PAPER / g
        if p.is_file():
            defined |= set(DEFINED.findall(p.read_text()))
    defined |= set(DEFINED.findall((PAPER / 'main.tex').read_text()))
    bad = []
    for f in files:
        for n, line in enumerate(f.read_text().splitlines(), 1):
            text = line
            for rx, sub in STRIP:
                text = rx.sub(sub, text)
            for m in re.finditer(r'\d', text):
                bad.append(f'{f.relative_to(PAPER)}:{n}: a typed number: {line.strip()[:100]}')
                break
            for m in USED.findall(line.split('%')[0]):
                if m not in defined and m not in ('LaTeX', 'TeX'):
                    bad.append(f'{f.relative_to(PAPER)}:{n}: \\{m} is not defined by the data')
    for b in bad:
        print(b)
    print(f'lint_tex: {len(files)} files, {len(bad)} problem(s)')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
