"""Minimal S-expression parser/serializer for KiCad files.

Atoms are kept as Python str. Quoted strings are wrapped in Q so they are written back quoted.
"""
import re

class Q(str):
    """A quoted string atom."""

_tok = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


def parse(text):
    stack, cur = [], []
    pos = 0
    n = len(text)
    while pos < n:
        m = _tok.match(text, pos)
        if not m:
            if text[pos:].strip() == '':
                break
            raise ValueError(f'parse error at {pos}: {text[pos:pos+40]!r}')
        pos = m.end()
        if m.group(1):
            stack.append(cur)
            cur = []
        elif m.group(2):
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif m.group(3) is not None:
            cur.append(Q(m.group(3).replace('\\"', '"').replace('\\\\', '\\')))
        else:
            cur.append(m.group(4))
    assert not stack, 'unbalanced'
    return cur[0] if len(cur) == 1 else cur


def _atom(a):
    if isinstance(a, Q):
        return '"' + a.replace('\\', '\\\\').replace('"', '\\"') + '"'
    if isinstance(a, float):
        s = f'{a:.6f}'.rstrip('0').rstrip('.')
        return s if s not in ('-0', '') else '0'
    return str(a)


def dumps(e, indent=0):
    if not isinstance(e, list):
        return _atom(e)
    simple = all(not isinstance(x, list) for x in e)
    if simple:
        return '(' + ' '.join(_atom(x) for x in e) + ')'
    pad = '\t' * (indent + 1)
    out = '(' + ' '.join(_atom(x) for x in e if not isinstance(x, list))
    for x in e:
        if isinstance(x, list):
            out += '\n' + pad + dumps(x, indent + 1)
    return out + '\n' + '\t' * indent + ')'


def find(e, key):
    """First child list whose head is key."""
    for x in e:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def findall(e, key):
    return [x for x in e if isinstance(x, list) and x and x[0] == key]
