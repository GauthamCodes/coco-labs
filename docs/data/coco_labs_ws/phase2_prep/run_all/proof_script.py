"""Throwaway breaks of coco_lab/test/test_search.py for proving run_all_package_tests.sh fails.

usage: proof_script.py <repo> failure|collection
"""
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / 'coco_lab' / 'test' / 'test_search.py'
s = path.read_text()
if sys.argv[2] == 'failure':
    old = "                          'weighted_astar')\n"
    new = "                          'weighted_astar', 'THROWAWAY_BREAK')\n"
    assert s.count(old) == 1
    s = s.replace(old, new, 1)
else:
    first_def = s.index('\ndef test_exactly_five_algorithms')
    s = s[:first_def] + '\nimport coco_lab_throwaway_module_that_does_not_exist  # noqa\n' + s[first_def:]
path.write_text(s)
print('broke', path, 'with', sys.argv[2])
