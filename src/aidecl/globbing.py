"""Path globs, modelled on REUSE.toml.

* ``*``   matches any characters except ``/``
* ``**``  matches any characters including ``/`` (``**/`` also matches nothing)
* ``?``   matches one character except ``/``
* ``\\*``, ``\\?``, ``\\\\`` match a literal ``*``, ``?`` or backslash

Patterns are relative to the directory of AIDECL.toml and always use ``/``.
"""
from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=None)
def compile_glob(pattern: str) -> re.Pattern:
    if pattern.startswith("./"):
        pattern = pattern[2:]
    out, i, n = [], 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "\\" and i + 1 < n:
            out.append(re.escape(pattern[i + 1]))
            i += 2
        elif pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("".join(out) + r"\Z", re.DOTALL)


def matches(pattern: str, path: str) -> bool:
    return compile_glob(pattern).match(path) is not None


def escape(literal: str) -> str:
    """A pattern that matches exactly the given path."""
    return "".join("\\" + c if c in "*?\\" else c for c in literal)
