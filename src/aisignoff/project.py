"""Finding the files of a project and resolving each file's declaration."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from . import inline
from .config import FILENAME, LEGACY_FILENAME, Config, load
from .model import AXES, Declaration, validate

ALWAYS_SKIPPED = {FILENAME, LEGACY_FILENAME}


class ProjectError(Exception):
    pass


def _inside_git(root: Path) -> bool:
    return any((p / ".git").exists() for p in (root, *root.parents))


def list_files(root: Path) -> list[str]:
    """Files of the project, relative to root with '/' separators.

    In a git work tree: tracked files plus untracked files that are not ignored
    (so .gitignore is respected). Outside git: every file below root except .git/.
    """
    if _inside_git(root):
        try:
            out = subprocess.run(
                ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                capture_output=True, check=True,
            ).stdout
        except FileNotFoundError:
            raise ProjectError("this is a git repository, but git is not installed, so .gitignore "
                               "cannot be respected")
        except subprocess.CalledProcessError as e:
            message = e.stderr.decode("utf-8", "replace").strip()
            raise ProjectError(f"git ls-files failed: {message}")
        names = sorted({n for n in out.decode("utf-8", "surrogateescape").split("\0") if n})
        return [n for n in names if (root / n).is_file() or (root / n).is_symlink()]
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for f in filenames:
            found.append(Path(dirpath, f).relative_to(root).as_posix())
    return sorted(found)


@dataclass
class FileResult:
    path: str
    declaration: Declaration
    errors: list[str]


def _merge_closest(own: Declaration, fallback: Declaration | None) -> Declaration:
    """Inline tags win per axis; a missing axis is taken from SIGNOFF.toml.

    The axes are generation (AI-Generation + Assisted-by), human review
    (Human-Review + Reviewed-by) and AI review (AI-Review + AI-Reviewed-by). An axis counts
    as given inline when its level line is present.
    """
    stray = [f"inline {names} without an inline {level} line"
             for level, names in AXES if own.get(level) is None and own.get(names)]
    if stray:
        own = replace(own, problems=own.problems + stray)
    if fallback is None:
        return own
    updates = {}
    for level, names in AXES:
        if own.get(level) is None and fallback.get(level) is not None:
            updates[Declaration._FIELDS[level]] = fallback.get(level)
            updates[Declaration._FIELDS[names]] = fallback.get(names)
    if not updates:
        return own
    return replace(own, **updates, source=f"inline + {fallback.source}", problems=list(own.problems))


def resolve(root: Path, config: Config, path: str) -> Declaration:
    """Declaration of one file. With precedence "closest" (default), inline tags win and
    SIGNOFF.toml fills a missing axis; with "override", the annotation alone counts."""
    annotation = config.match(path)
    if annotation is not None and annotation.precedence == "override":
        return annotation.declaration()
    found = inline.parse(root / path)
    if found is not None:
        return _merge_closest(found, annotation.declaration() if annotation else None)
    if annotation is not None:
        return annotation.declaration()
    return Declaration()


class Project:
    def __init__(self, root: Path):
        root = Path(root)
        if not root.is_dir():
            raise ProjectError(f"project root {root} is not a directory")
        self.root = root.resolve()
        self.config = load(self.root)

    def files(self) -> list[str]:
        return [f for f in list_files(self.root)
                if f not in ALWAYS_SKIPPED and not self.config.is_excluded(f)]

    def results(self) -> list[FileResult]:
        out = []
        for f in self.files():
            d = resolve(self.root, self.config, f)
            out.append(FileResult(f, d, validate(d, self.config.policy)))
        return out

    def unused_annotations(self, files: list[str]) -> list[int]:
        return [a.index for a in self.config.annotations if not any(a.matches(f) for f in files)]
