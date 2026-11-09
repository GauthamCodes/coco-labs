"""
R3: every GitHub workflow is YAML that GitHub would accept as far as keys go.

PyYAML silently keeps the last of two equal keys; GitHub rejects the file ("workflow file
issue"). A duplicated `if:` in leaderboard-results.yml passed a plain yaml.safe_load and failed
every run (found 2026-11-07), so every mapping is checked for duplicate keys here.
"""
from pathlib import Path

import pytest
import yaml

WORKFLOWS = sorted((Path(__file__).resolve().parents[2] / '.github' / 'workflows').glob('*.yml'))


class _Strict(yaml.SafeLoader):
    pass


def _no_dupes(loader, node, deep=False):
    seen = set()
    for k, _ in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(None, None, f'duplicate key {key!r}',
                                                    k.start_mark)
        seen.add(key)
    return loader.construct_mapping(node, deep)


_Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_dupes)


@pytest.mark.parametrize('path', WORKFLOWS, ids=lambda p: p.name)
def test_no_duplicate_keys(path):
    doc = yaml.load(path.read_text(), Loader=_Strict)
    assert isinstance(doc, dict) and 'jobs' in doc


def test_the_strict_loader_catches_a_duplicate():
    with pytest.raises(yaml.constructor.ConstructorError):
        yaml.load('a: 1\na: 2\n', Loader=_Strict)
