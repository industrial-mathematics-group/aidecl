"""Reading AIDECL.toml.

Format::

    version = 3
    exclude = ["docs/build/**"]          # optional: files that need no declaration

    [policy]                             # optional: minimum review levels per generation level
    "*" = { human = "H1" }
    G3  = { human = "H2", ai = "A2" }

    [[annotations]]
    path = "**"                          # one pattern or a list of patterns
    precedence = "closest"               # optional: "closest" (default) or "override"
    AI-Generation = "G0"
    Human-Review = "H2"
    AI-Review = "A0"
    Reviewed-by = "Jane Doe"             # string or list of strings
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .globbing import compile_glob, matches
from .model import KEYS, LEVELS, LIST_KEYS, TODO, Declaration, Policy, canonical_key, parse_policy

FILENAME = "AIDECL.toml"
VERSION = 3
PRECEDENCES = ("closest", "override")


class ConfigError(Exception):
    pass


class LegacyConfig(ConfigError):
    """AIDECL.toml still uses version 1 (V0-V3 levels)."""


@dataclass
class Annotation:
    index: int  # 1-based position in the file
    paths: tuple[str, ...]
    precedence: str
    values: dict

    def matches(self, path: str) -> bool:
        return any(matches(p, path) for p in self.paths)

    def declaration(self) -> Declaration:
        return Declaration.from_mapping(self.values, source=f"{FILENAME} [{self.index}]")


@dataclass
class Config:
    path: Path | None
    annotations: list[Annotation] = field(default_factory=list)
    exclude: tuple[str, ...] = ()
    policy: Policy = field(default_factory=Policy)

    def is_excluded(self, path: str) -> bool:
        return any(matches(p, path) for p in self.exclude)

    def match(self, path: str) -> Annotation | None:
        """The last annotation that matches wins (same rule as REUSE.toml)."""
        found = None
        for a in self.annotations:
            if a.matches(path):
                found = a
        return found


def _str_list(value, what: str) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{what} must be a string or a list of strings")
    return tuple(value)


def read_toml(root: Path) -> dict | None:
    path = root / FILENAME
    if not path.exists():
        return None
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{FILENAME}: invalid TOML: {e}") from e


def load(root: Path) -> Config:
    data = read_toml(root)
    if data is None:
        return Config(path=None)
    path = root / FILENAME

    version = data.get("version")
    if type(version) is int and version in (1, 2):
        old = "V0-V3 levels" if version == 1 else "the AI review scale A-, A0-A3"
        raise LegacyConfig(f"{FILENAME} uses version {version} ({old}). Run 'aidecl migrate' to convert "
                           f"it to version {VERSION}.")
    if type(version) is not int or version != VERSION:
        raise ConfigError(f"{FILENAME}: 'version = {VERSION}' is required")
    unknown = set(data) - {"version", "exclude", "policy", "annotations"}
    if unknown:
        raise ConfigError(f"{FILENAME}: unknown top-level key(s): {', '.join(sorted(unknown))}")
    exclude = _str_list(data.get("exclude", []), f"{FILENAME}: 'exclude'")
    for p in exclude:
        compile_glob(p)
    try:
        policy = parse_policy(data.get("policy"), where=f"{FILENAME} [policy]")
    except ValueError as e:
        raise ConfigError(str(e)) from e

    annotations = []
    raw = data.get("annotations", [])
    if not isinstance(raw, list) or not all(isinstance(t, dict) for t in raw):
        raise ConfigError(f"{FILENAME}: use [[annotations]] tables")
    for i, table in enumerate(raw, start=1):
        where = f"{FILENAME} annotation [{i}]"
        if "path" not in table:
            raise ConfigError(f"{where}: 'path' is required")
        paths = _str_list(table["path"], f"{where}: 'path'")
        if not paths or any(p == "" for p in paths):
            raise ConfigError(f"{where}: 'path' must not be empty")
        precedence = table.get("precedence", "closest")
        if precedence not in PRECEDENCES:
            raise ConfigError(f"{where}: precedence must be 'closest' or 'override'")
        values = {}
        for k, v in table.items():
            if k in ("path", "precedence"):
                continue
            key = canonical_key(k)
            if key is None:
                raise ConfigError(f"{where}: unknown key '{k}' (allowed: {', '.join(KEYS)})")
            if key in values:
                raise ConfigError(f"{where}: '{key}' is given more than once")
            if key in LIST_KEYS:
                values[key] = _str_list(v, f"{where}: '{k}'")
            else:
                if not isinstance(v, str):
                    raise ConfigError(f"{where}: '{k}' must be a string")
                if v not in LEVELS[key] and v != TODO:  # TODO: placeholder, reported by lint
                    raise ConfigError(f"{where}: invalid {key} '{v}' (use {', '.join(LEVELS[key])})")
                values[key] = v
        annotations.append(Annotation(index=i, paths=paths, precedence=precedence, values=values))
    return Config(path=path, annotations=annotations, exclude=exclude, policy=policy)
