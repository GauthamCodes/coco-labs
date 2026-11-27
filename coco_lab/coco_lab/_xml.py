# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
R5.4: the subset of ``xml.etree.ElementTree`` that :mod:`coco_lab.worldgen` uses, for Pyodide.

Pyodide's standard library has no ``xml`` package ("removed ... due to browser limitations"), so
the browser could not generate a level's SDF (the level's ROS 2 package, R5.4; the world editor,
R5.5). Native Python keeps using the standard library: ``worldgen`` imports this only when ``xml``
is missing. What is here reproduces CPython 3.12's behaviour for that subset -- the parser for a
well-formed document without DTD, CDATA or namespaces (COCO's templates), ``find``/``findall``/
``iter`` paths ``tag``, ``a/b``, ``.//a/b``, ``indent`` and ``tostring(encoding='unicode')`` with
CPython's escaping -- and ``coco_lab/test/test_xml_shim.py`` holds it to byte-identical output
against the standard library for every World Spec in the repository.
"""
import re

__all__ = ['Element', 'SubElement', 'fromstring', 'indent', 'tostring']

_ENTITY = {'lt': '<', 'gt': '>', 'amp': '&', 'quot': '"', 'apos': "'"}


class Element:
    """An element: ``tag``, ``attrib`` (insertion order), ``text``, ``tail`` and children."""

    def __init__(self, tag, attrib=None, **extra):
        self.tag = tag
        self.attrib = dict(attrib or {}, **extra)
        self.text = None
        self.tail = None
        self._children = []

    def __len__(self):
        return len(self._children)

    def __iter__(self):
        return iter(self._children)

    def __getitem__(self, i):
        return self._children[i]

    def __bool__(self):  # as ElementTree warns: test `is None`, not truth
        return True

    def append(self, el):
        self._children.append(el)

    def insert(self, i, el):
        self._children.insert(i, el)

    def remove(self, el):
        self._children.remove(el)

    def get(self, key, default=None):
        return self.attrib.get(key, default)

    def set(self, key, value):  # noqa: A003 (ElementTree's own name)
        self.attrib[key] = value

    def items(self):
        return list(self.attrib.items())

    def iter(self, tag=None):  # noqa: A003 (ElementTree's own name)
        if tag is None or self.tag == tag:
            yield self
        for c in self._children:
            yield from c.iter(tag)

    def findall(self, path):
        return list(_select(self, path))

    def find(self, path):
        for e in _select(self, path):
            return e
        return None


def SubElement(parent, tag, attrib=None, **extra):  # noqa: N802 (ElementTree's name)
    el = Element(tag, attrib, **extra)
    parent.append(el)
    return el


def _select(el, path):
    """Select by the ElementTree paths worldgen uses: 'tag', 'a/b', './/a/b' (descendants)."""
    if path.startswith('.//'):
        steps = path[3:].split('/')
        first = [d for c in el for d in c.iter(steps[0])]
    else:
        steps = path.split('/')
        first = [c for c in el if c.tag == steps[0]]
    current = first
    for step in steps[1:]:
        current = [c for e in current for c in e if c.tag == step]
    return current


_TOKEN = re.compile(
    r'<\?.*?\?>|<!--.*?-->|<(/?)([A-Za-z_][\w.:-]*)'
    r'((?:\s+[\w.:-]+\s*=\s*(?:"[^"]*"|\'[^\']*\'))*)\s*(/?)>',
    re.S,
)
_ATTR = re.compile(r'([\w.:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')


def _unescape(s):
    def one(m):
        e = m.group(1)
        if e.startswith('#x'):
            return chr(int(e[2:], 16))
        if e.startswith('#'):
            return chr(int(e[1:]))
        if e in _ENTITY:
            return _ENTITY[e]
        raise ValueError(f'undefined entity &{e};')

    return re.sub(r'&(#x[0-9A-Fa-f]+|#[0-9]+|\w+);', one, s)


def fromstring(text):
    """Parse a well-formed document (no DTD, CDATA or namespaces) into its root Element."""
    stack, root, last, pos = [], None, None, 0
    for m in _TOKEN.finditer(text):
        between = text[pos:m.start()]
        pos = m.end()
        if between:
            if '<' in between:
                raise ValueError(f'not well-formed near offset {m.start()}')
            s = _unescape(between)
            if last is not None:  # after a closed element: its tail
                last.tail = (last.tail or '') + s
            elif stack:  # after an opening tag: the parent's text
                stack[-1].text = (stack[-1].text or '') + s
            elif s.strip():
                raise ValueError('text outside the root element')
        if m.group(0).startswith(('<?', '<!--')):
            continue
        closing, tag, attrs, selfclose = m.group(1), m.group(2), m.group(3), m.group(4)
        if closing:
            if not stack or stack[-1].tag != tag:
                raise ValueError(f'mismatched </{tag}>')
            last = stack.pop()
            continue
        el = Element(
            tag,
            {
                a.group(1): _unescape(a.group(2) if a.group(2) is not None else a.group(3))
                for a in _ATTR.finditer(attrs)
            },
        )
        if stack:
            stack[-1].append(el)
        elif root is None:
            root = el
        else:
            raise ValueError('more than one root element')
        if selfclose:
            last = el
        else:
            stack.append(el)
            last = None
    if stack or root is None:
        raise ValueError('not well-formed: unclosed elements or no root')
    if text[pos:].strip():
        raise ValueError('text after the root element')
    return root


def indent(tree, space='  ', level=0):
    """Indent as CPython 3.12's ``ElementTree.indent`` does, verbatim in behaviour."""
    if level < 0:
        raise ValueError(f'Initial indentation level must be >= 0, got {level}')
    if not len(tree):
        return
    indentations = ['\n' + level * space]

    def _indent_children(elem, level):
        child_level = level + 1
        try:
            child_indentation = indentations[child_level]
        except IndexError:
            child_indentation = indentations[level] + space
            indentations.append(child_indentation)
        if not elem.text or not elem.text.strip():
            elem.text = child_indentation
        for child in elem:
            if len(child):
                _indent_children(child, child_level)
            if not child.tail or not child.tail.strip():
                child.tail = child_indentation
        if not child.tail.strip():
            child.tail = indentations[level]

    _indent_children(tree, 0)


def _escape_cdata(s):
    if '&' in s:
        s = s.replace('&', '&amp;')
    if '<' in s:
        s = s.replace('<', '&lt;')
    if '>' in s:
        s = s.replace('>', '&gt;')
    return s


def _escape_attrib(s):
    for a, b in (
        ('&', '&amp;'),
        ('<', '&lt;'),
        ('>', '&gt;'),
        ('"', '&quot;'),
        ('\r', '&#13;'),
        ('\n', '&#10;'),
        ('\t', '&#09;'),
    ):
        if a in s:
            s = s.replace(a, b)
    return s


def _serialize(write, elem):
    write('<' + elem.tag)
    for k, v in elem.attrib.items():
        write(' %s="%s"' % (k, _escape_attrib(str(v))))
    if elem.text or len(elem):
        write('>')
        if elem.text:
            write(_escape_cdata(elem.text))
        for e in elem:
            _serialize(write, e)
        write('</' + elem.tag + '>')
    else:
        write(' />')
    if elem.tail:
        write(_escape_cdata(elem.tail))


def tostring(element, encoding='unicode'):
    """
    Serialize ``element`` to a str, as ElementTree's ``tostring`` does.

    Only ``encoding='unicode'``, the one form worldgen uses.
    """
    if encoding != 'unicode':
        raise ValueError("this shim serializes to str only (encoding='unicode')")
    out = []
    _serialize(out.append, element)
    return ''.join(out)
