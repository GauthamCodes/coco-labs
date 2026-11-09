#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R2.6: the leaderboard's trusted writer (.github/workflows/leaderboard-results.yml; ADR 0012).

    leaderboard_writer.py VERIFICATION_DIR          the workflow: validate, comment, label, commit
    leaderboard_writer.py --compare OLD.json NEW.json   re-verify: same result? (exit 1 if not)

Standard library and the `gh` CLI only. The verifier's artifact is UNTRUSTED DATA: every field
used is type- and size-checked, nothing in it is executed, and the PR comment is regenerated from
the checked numbers (no text from the artifact is posted verbatim). The pull request number
claimed by the artifact is checked against the API (the PR whose head is the verified commit),
and the PR's changed files are checked again: only its submission directories.
"""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SCHEMA = 'coco.leaderboard.entry.v1'
NAME = re.compile(r'^[a-z0-9][a-z0-9_-]{1,39}$')
SUITE = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
SHA = re.compile(r'^[0-9a-f]{40}$')
FILES = re.compile(r'^leaderboard/submissions/([a-z0-9-]+)/([a-z0-9][a-z0-9_-]{1,39})/'
                   r'(algorithm\.py|meta\.yaml|summary\.json)$')
#: R3 Part A: this writer's own commit to a same-repository PR (the verified result); allowed
#: only for a submission the PR makes, and only while it equals the verified result
RESULT = re.compile(r'^leaderboard/results/([a-z0-9-]+)/([a-z0-9][a-z0-9_-]{1,39})/result\.json$')
MAX_BYTES = 8 * 1024 * 1024
#: what may differ between two verifications of the same entry: the machine, and (R3.3, ADR
#: 0014) the secret held-out result, drawn fresh for every head (a re-commit for it would loop)
VOLATILE = ('host', 'held_out_secret')


class Invalid(ValueError):
    """The artifact is not what the verifier writes."""


def _num(v, where, lo=None, hi=None, none=True):
    if v is None and none:
        return v
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float('inf'),
                                                                               float('-inf')):
        raise Invalid(f'{where}: not a finite number')
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise Invalid(f'{where}: out of range')
    return v


def _text(v, where, n=2000, none=False):
    if v is None and none:
        return v
    if not isinstance(v, str) or len(v) > n:
        raise Invalid(f'{where}: not a short string')
    return v


def validate(r: dict) -> dict:
    """Check every field the writer uses; return the result."""
    if not isinstance(r, dict) or r.get('schema') != SCHEMA:
        raise Invalid('not a coco.leaderboard.entry.v1')
    if not isinstance(r.get('verified'), bool):
        raise Invalid('verified is true or false')
    if not isinstance(r.get('problems'), list) or len(r['problems']) > 50:
        raise Invalid('problems')
    for i, p in enumerate(r['problems']):
        _text(p, f'problems[{i}]')
    e = r.get('entry')
    if e is None:
        return r
    if not (isinstance(e, dict) and NAME.match(str(e.get('name'))) and
            SUITE.match(str(e.get('suite')))):
        raise Invalid('entry name / suite')
    for k in ('display_name', 'author', 'description', 'licence', 'family', 'kind'):
        _text(e.get(k), f'entry.{k}')
    if e['licence'] not in ('MIT', 'Apache-2.0') or e['family'] not in (
            'planning', 'control', 'localisation') or e['kind'] not in ('submission', 'builtin'):
        raise Invalid('entry licence / family / kind')
    _text(e.get('paper'), 'entry.paper', 500, none=True)
    # the verify job's read_meta already requires https://; the writer re-checks (a PR controls its workflow file)
    if e.get('paper') is not None and not re.fullmatch(r'https://[^\s"\'<>`]+', e['paper']):
        raise Invalid('entry.paper is an https:// URL')
    for part in ('public', 'held_out'):
        s = (r.get(part) or {}).get('score')
        if not isinstance(s, dict):
            raise Invalid(f'{part}.score')
        _num(s.get('n'), f'{part}.n', 0, 100000, none=False)
        _num(s.get('successes'), f'{part}.successes', 0, s['n'], none=False)
        for k, v in s.items():
            if isinstance(v, dict):
                for kk in ('n', 'median', 'q1', 'q3'):
                    _num(v.get(kk), f'{part}.{k}.{kk}')
    c = r.get('checks')
    if not isinstance(c, dict) or not isinstance(c.get('deterministic'), bool):
        raise Invalid('checks')
    _num(c.get('contract_problems'), 'checks.contract_problems', 0, none=False)
    return r


def _md(s) -> str:
    """Text from a submission, made inert in a comment (no mentions, links or markup)."""
    s = str(s).replace('\n', ' ')[:300]
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    s = re.sub(r'([\\`*_{}\[\]()#+!|~])', r'\\\1', s)
    return s.replace('@', '@\u200b')   # a zero-width space: never a mention


#: R3.3 (ADR 0014): the only keys a held-out aggregate may carry
AGG_KEYS = {'family', 'n', 'successes', 'wilson95', 'path_ratio_median', 'min_clearance_m_median',
            'time_s_median', 'final_err_xy_m_median', 'mean_err_xy_m_median'}


def validate_agg(a) -> dict:
    """A held-out aggregate from tools/r3/heldout.py: numbers only, its keys only."""
    if not isinstance(a, dict) or set(a) - AGG_KEYS or a.get('family') not in (
            'planning', 'control', 'localisation'):
        raise Invalid('held-out aggregate')
    _num(a.get('n'), 'held-out n', 1, 200, none=False)
    _num(a.get('successes'), 'held-out successes', 0, a['n'], none=False)
    w = a.get('wilson95')
    if not (isinstance(w, list) and len(w) == 2):
        raise Invalid('held-out wilson95')
    for v in w:
        _num(v, 'held-out wilson95', 0, 1, none=False)
    for k in AGG_KEYS - {'family', 'n', 'successes', 'wilson95'}:
        _num(a.get(k), f'held-out {k}', -1e6, 1e6)
    return a


def secret_heldout(agg_dir, suite, name):
    """The secret held-out aggregate of one entry: dict, 'none' (no secret configured) or None."""
    if agg_dir is None:
        return None
    root = Path(agg_dir)
    if (root / 'heldout' / 'NONE').exists() or (root / 'NONE').exists():
        return 'none'
    p = root / 'agg' / suite / f'{name}.json'
    if not p.is_file():
        p = root / suite / f'{name}.json'
    if not p.is_file() or p.stat().st_size > 10000:
        return None
    try:
        return validate_agg(json.loads(p.read_text()))
    except (Invalid, ValueError):
        return None


def comment(results, scope_ok, conclusion) -> str:
    """The PR comment, regenerated from the validated numbers."""
    ok = scope_ok and conclusion == 'success' and results and all(r['verified'] for _, r in results)
    lines = [f"### Leaderboard verification: {'VERIFIED' if ok else 'NOT VERIFIED'}", '',
             'Re-run natively by the base branch\'s verifier in a sandbox (no network, no secrets). '
             'MODEL evidence. Written by the trusted leaderboard-results workflow from the '
             'verifier\'s artifact.', '']
    if not scope_ok:
        lines.append('- This pull request changes files outside its submission directory; a '
                     'maintainer must review it by hand.')
    if conclusion != 'success':
        lines.append(f'- The verifier run ended `{_md(conclusion)}`.')
    for path, r in results:
        e = r.get('entry') or {}
        lines.append(f"**{_md(e.get('display_name', path))}** (`{_md(e.get('suite'))}/"
                     f"{_md(e.get('name'))}`, {_md(e.get('family'))}, {_md(e.get('licence'))})")
        for p in r['problems']:
            lines.append(f'- problem: {_md(p)}')
        for part in ('public', 'held_out'):
            s = (r.get(part) or {}).get('score')
            if s:
                txt = f"- {part.replace('_', '-')}: {s['successes']}/{s['n']} succeeded"
                for k in ('path_ratio', 'min_clearance_m', 'time_s', 'final_err_xy_m'):
                    if isinstance(s.get(k), dict) and s[k].get('median') is not None:
                        txt += f"; {k} median {float(s[k]['median']):.4g}"
                lines.append(txt)
        h = r.get('held_out_secret')
        if h == 'none':
            lines.append('- held-out (secret, ADR 0014): not run, no secret configured')
        elif isinstance(h, dict):
            txt = (f"- held-out (secret, ADR 0014; fresh for this head): {h['successes']}/{h['n']} "
                   f"succeeded (Wilson 95% {h['wilson95'][0]}-{h['wilson95'][1]})")
            for k in sorted(h):
                if k.endswith('_median') and h[k] is not None:
                    txt += f'; {k[:-7]} median {h[k]}'
            lines.append(txt)
        elif 'held_out_secret' in r:
            lines.append('- held-out (secret, ADR 0014): no valid result')
        c = r.get('checks') or {}
        if c:
            lines.append(f"- deterministic: {c.get('deterministic')}; contract problems: "
                         f"{c.get('contract_problems')}; claim matches: {c.get('claim_matches')}")
        lines.append('')
    return '\n'.join(lines)


def gh(*args, data=None) -> str:
    out = subprocess.run(['gh', *args], input=data, capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError(f'gh {args[:3]}: {out.stderr.strip()[:500]}')
    return out.stdout


def write(verification: Path) -> int:
    repo, head = os.environ['REPO'], os.environ['HEAD_SHA']
    conclusion = os.environ.get('CONCLUSION', '')
    if not SHA.match(head):
        raise Invalid('head sha')
    run = json.loads((verification / 'run.json').read_text()[:10000])
    pr = _num(run.get('pr'), 'pr', 1, none=False)
    prs = json.loads(gh('api', f'repos/{repo}/commits/{head}/pulls'))
    if pr not in [p['number'] for p in prs]:
        raise Invalid(f'PR #{pr} does not have {head} as a commit')
    files = json.loads(gh('api', '--paginate', '--slurp', f'repos/{repo}/pulls/{int(pr)}/files'))
    names = [f['filename'] for page in files for f in page]
    results = []
    for p in sorted(verification.glob('*/*/result.json')):
        if p.stat().st_size > MAX_BYTES:
            raise Invalid(f'{p}: too large')
        results.append((str(p.relative_to(verification)), validate(json.loads(p.read_text()))))
    agg_dir = os.environ.get('HELDOUT_DIR')
    for _, r in results:   # R3.3 (ADR 0014): the secret held-out aggregate of this head
        e = r.get('entry')
        if not agg_dir or not e:
            continue
        h = secret_heldout(agg_dir, e['suite'], e['name'])
        if h is None:
            r['held_out_secret'] = None
            r['problems'].append('the secret held-out run gave no valid result')
            r['verified'] = False
        else:
            r['held_out_secret'] = h if h == 'none' else dict(h, head=head)
    scope_ok, committed = in_scope(names)
    same_repo = os.environ.get('HEAD_REPO') == repo
    # a fork's result.json must be the verified one; on a same-repository branch (writable only
    # by maintainers) a stale one is simply overwritten below
    for suite, name in ([] if same_repo else committed):
        mine = [r for _, r in results if (r.get('entry') or {}).get('suite') == suite
                and (r.get('entry') or {}).get('name') == name]
        path = f'leaderboard/results/{suite}/{name}/result.json'
        theirs = _contents(repo, path, head)
        if not mine or theirs is None or stable(theirs) != stable(mine[0]):
            scope_ok = False
    ok = scope_ok and conclusion == 'success' and results and all(r['verified'] for _, r in results)
    for label, colour in (('verified', '1f883d'), ('not-verified', 'cf222e')):
        gh('label', 'create', label, '--repo', repo, '--color', colour, '--force')
    gh('pr', 'comment', str(int(pr)), '--repo', repo, '--body-file', '-',
       data=comment(results, scope_ok, conclusion))
    gh('pr', 'edit', str(int(pr)), '--repo', repo, '--add-label',
       'verified' if ok else 'not-verified', '--remove-label', 'not-verified' if ok else 'verified')
    if ok and same_repo:
        branch = os.environ['HEAD_BRANCH']
        for rel, r in results:
            e = r['entry']
            path = f"leaderboard/results/{e['suite']}/{e['name']}/result.json"
            old = _contents(repo, path, branch)
            if old is not None and stable(old) == stable(r):
                continue   # already there: no commit, so no new run of this workflow
            body = {'message': f"[leaderboard] verified result for {e['suite']}/{e['name']}",
                    'content': base64.b64encode((json.dumps(r, indent=1, sort_keys=True) + '\n')
                                                .encode()).decode(), 'branch': branch}
            try:
                body['sha'] = json.loads(gh('api', f'repos/{repo}/contents/{path}?ref={branch}'))['sha']
            except RuntimeError:
                pass
            gh('api', '-X', 'PUT', f'repos/{repo}/contents/{path}', '--input', '-',
               data=json.dumps(body))
    print('verified' if ok else 'not verified')
    return 0


def in_scope(names):
    """(every changed file allowed?, the (suite, name) of each result.json among them)."""
    subs = {FILES.match(n).groups()[:2] for n in names if FILES.match(n)}
    results = [RESULT.match(n).groups() for n in names if RESULT.match(n)]
    ok = bool(subs) and all(FILES.match(n) or (RESULT.match(n) and
                                                RESULT.match(n).groups() in subs) for n in names)
    return ok, sorted(set(results) & subs)


def _contents(repo, path, ref):
    """The JSON file at ``ref`` through the API (None if absent or not a small JSON object)."""
    try:
        meta = json.loads(gh('api', f'repos/{repo}/contents/{path}?ref={ref}'))
        if not isinstance(meta, dict) or meta.get('size', MAX_BYTES + 1) > MAX_BYTES:
            return None
        if meta.get('content'):
            raw = base64.b64decode(meta['content'])
        else:   # over the contents API's 1 MB inline limit: the blob
            blob = json.loads(gh('api', f"repos/{repo}/git/blobs/{meta['sha']}"))
            raw = base64.b64decode(blob['content'])
        r = json.loads(raw.decode())
        return r if isinstance(r, dict) else None
    except (RuntimeError, ValueError, KeyError):
        return None


def stable(r):
    """A result without what may differ between two verifications of it (the machine, times)."""
    r = {k: v for k, v in r.items() if k not in VOLATILE}
    for part in ('public', 'held_out'):
        if isinstance(r.get(part), dict) and isinstance(r[part].get('score'), dict):
            r[part] = dict(r[part], score={k: v for k, v in r[part]['score'].items()
                                            if k != 'compute_ms'})
    return r


def compare(old: Path, new: Path) -> int:
    a, b = json.loads(old.read_text()), json.loads(new.read_text())
    if stable(a) != stable(b):
        print(f'DIFFERS: {old} (committed) vs {new} (re-verified)')
        return 1
    print(f'same: {old}')
    return 0


if __name__ == '__main__':
    if sys.argv[1] == '--compare':
        raise SystemExit(compare(Path(sys.argv[2]), Path(sys.argv[3])))
    raise SystemExit(write(Path(sys.argv[1])))
