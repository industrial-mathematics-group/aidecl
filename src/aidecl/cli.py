"""Command-line interface: aidecl init | lint | report | annotate | badge."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import __version__, inline
from .config import FILENAME, ConfigError, load
from .globbing import escape
from .model import (ASSISTED, GEN, GENERATION, TESTED, VER, VERIFICATION, VERIFIED, Declaration,
                    validate)
from .project import Project, ProjectError

SPEC_URL = ("https://github.com/industrial-mathematics-group/.github/blob/main/.github/"
            "CONTRIBUTING.md#ai-assisted-contributions")


class UsageError(Exception):
    pass


def _toml_str(s: str) -> str:
    # JSON string escapes are valid TOML basic-string escapes; DEL is the one control
    # character JSON leaves unescaped but TOML forbids.
    return json.dumps(s, ensure_ascii=False).replace("\x7f", "\\u007f")


def _toml_value(v) -> str:
    if isinstance(v, str):
        return _toml_str(v)
    return "[" + ", ".join(_toml_str(x) for x in v) + "]"


def _values(args) -> dict:
    values = {GEN: args.generation, VER: args.verification}
    for key, items in ((ASSISTED, args.assisted_by), (VERIFIED, args.verified_by), (TESTED, args.tested_by)):
        if items:
            for item in items:
                if not item.strip() or any(ord(c) < 32 or ord(c) == 127 for c in item):
                    raise UsageError(f"{key} values must be non-empty single-line text: {item!r}")
            values[key] = [i.strip() for i in items]
    return values


def _check_complete(values: dict) -> list[str]:
    return validate(Declaration.from_mapping(values, source="command line"))


def _open(root) -> Project:
    try:
        return Project(root)
    except (ConfigError, ProjectError) as e:
        raise UsageError(str(e))


def _results(project: Project):
    try:
        return project.results()
    except ProjectError as e:
        raise UsageError(str(e))


def _status_level(r, which: str) -> str:
    """Level for counting: the declared level if the declaration is valid, else 'undeclared'."""
    if r.errors:
        return "undeclared"
    return r.declaration.generation if which == "G" else r.declaration.verification


# ---------------------------------------------------------------- init
def cmd_init(args) -> int:
    root = Path(args.root)
    if not root.is_dir():
        raise UsageError(f"project root {root} is not a directory")
    target = root / FILENAME
    if target.exists():
        raise UsageError(f"{target} already exists")
    lines = [
        "# AI declarations for this repository (G0-G3 generation, V0-V3 verification).",
        f"# Scheme: {SPEC_URL}",
        "# The LAST annotation that matches a file wins. Inline tags in a file win over",
        '# this file unless the matching annotation sets precedence = "override".',
        "version = 1",
        "",
        '# exclude = ["docs/build/**"]   # files that need no declaration',
        "",
    ]
    if args.generation or args.verification:
        if not (args.generation and args.verification):
            raise UsageError("give both --generation and --verification, or neither")
        values = _values(args)
        problems = _check_complete(values)
        if problems:
            raise UsageError("incomplete declaration: " + "; ".join(problems))
        lines += ["# Default for everything", "[[annotations]]", 'path = "**"']
        lines += [f"{k} = {_toml_value(v)}" for k, v in values.items()]
    else:
        lines += [
            "# Example:",
            "# [[annotations]]",
            '# path = "**"',
            '# AI-Generation = "G0"',
            '# AI-Verification = "V0"',
            '# Tested-by = "Jane Doe"',
        ]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Created {target}")
    return 0


# ---------------------------------------------------------------- lint
def cmd_lint(args) -> int:
    project = _open(args.root)
    results = _results(project)
    if not results:
        print(f"✗ no files found below {project.root}")
        return 1
    files = [r.path for r in results]
    by_error = defaultdict(list)
    for r in results:
        for e in r.errors:
            by_error[e].append(r.path)
    unused = project.unused_annotations(files)

    for error, paths in sorted(by_error.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"✗ {error}: {len(paths)} file(s)")
        for p in paths[: args.max_files]:
            print(f"    {p}")
        if len(paths) > args.max_files:
            print(f"    … and {len(paths) - args.max_files} more")
    for index in unused:
        print(f"{'✗' if args.strict else '!'} {FILENAME} annotation [{index}] matches no file")

    bad = sum(1 for r in results if r.errors)
    print()
    print(f"{len(results) - bad} of {len(results)} files have a valid declaration.")
    failed = bad > 0 or (args.strict and unused)
    if failed:
        print(f"See {SPEC_URL}")
    else:
        print("All files are declared. ✓")
    return 1 if failed else 0


# ---------------------------------------------------------------- report
def cmd_report(args) -> int:
    project = _open(args.root)
    results = _results(project)
    if args.json:
        print(json.dumps([{"path": r.path, **r.declaration.as_dict(), "errors": r.errors} for r in results],
                         indent=2, ensure_ascii=False))
        return 0
    if args.files:
        width = max((len(r.path) for r in results), default=4)
        for r in results:
            d = r.declaration
            status = "✓" if not r.errors else "✗"
            line = f"{status} {r.path:<{width}}  {d.generation or '--'} {d.verification or '--'}  ({d.source})"
            if r.errors:
                line += "  " + "; ".join(r.errors)
            print(line)
        return 0
    gen = Counter(_status_level(r, "G") for r in results)
    ver = Counter(_status_level(r, "V") for r in results)
    total = len(results) or 1
    print(f"{len(results)} files\n")
    for title, counts, levels in (("Generation", gen, GENERATION), ("Verification", ver, VERIFICATION)):
        print(title)
        for level, name in list(levels.items()) + [("undeclared", "missing or invalid declaration")]:
            if counts[level]:
                print(f"  {level:<10} {name:<36} {counts[level]:>5}  {100 * counts[level] / total:5.1f}%")
        print()
    return 0


# ---------------------------------------------------------------- annotate
def _real(path: str) -> str:
    """Absolute path with symlinked directories resolved, but not the last component."""
    a = os.path.abspath(path)
    return os.path.join(os.path.realpath(os.path.dirname(a)), os.path.basename(a))


def _pattern(root: Path, arg: str) -> str:
    """Turn a command-line argument into a pattern relative to the project root.

    Existing files and directories are escaped so they match exactly (even with * or ?
    in their name); symlinks are not followed. Anything else is a glob, taken relative
    to the current directory like the shell would.
    """
    root_real = os.path.realpath(root)
    if os.path.lexists(arg):
        if os.path.realpath(arg) == root_real:
            return "**"  # the project root itself, also when named through a symlink
        full = _real(arg)
        rel = os.path.relpath(full, root_real)
        if rel == ".." or rel.startswith(".." + os.sep) or os.path.isabs(rel):
            raise UsageError(f"{arg} is outside the project root {root}")
        rel = Path(rel).as_posix()
        if os.path.isdir(full) and not os.path.islink(full):
            return "**" if rel == "." else escape(rel) + "/**"
        return escape(rel)
    if not any(c in arg for c in "*?"):
        raise UsageError(f"{arg} does not exist (quote glob patterns)")
    if os.path.isabs(arg) or ".." in Path(arg).parts:
        raise UsageError(f"glob {arg!r}: use a pattern relative to the current directory, without '..'")
    pattern = arg.removeprefix("./")
    cwd_rel = os.path.relpath(os.path.realpath(os.getcwd()), root_real)
    if cwd_rel == ".." or cwd_rel.startswith(".." + os.sep):
        return pattern  # working outside the project: globs are relative to the root
    if cwd_rel != ".":
        pattern = escape(Path(cwd_rel).as_posix()) + "/" + pattern
    return pattern


def cmd_annotate(args) -> int:
    root = Path(args.root)
    values = _values(args)
    problems = _check_complete(values)
    if problems:
        raise UsageError("incomplete declaration: " + "; ".join(problems))

    if args.inline:
        if args.precedence:
            raise UsageError("--precedence only applies to AIDECL.toml, not to --inline")
        status = 0
        for arg in args.paths:
            path = Path(arg)
            try:
                inline.write(path, values)
                print(f"Tagged {path}")
            except (ValueError, OSError, UnicodeDecodeError) as e:
                print(f"aidecl annotate: {e}", file=sys.stderr)
                status = 1
        return status

    if not root.is_dir():
        raise UsageError(f"project root {root} is not a directory")
    patterns = [_pattern(root, a) for a in args.paths]
    target = root / FILENAME
    old = target.read_text(encoding="utf-8") if target.exists() else None
    text = old if old is not None else "version = 1\n"
    if not text.endswith("\n"):
        text += "\n"
    block = ["", "[[annotations]]",
             f"path = {_toml_value(patterns[0] if len(patterns) == 1 else patterns)}"]
    if args.precedence:
        block.append(f'precedence = "{args.precedence}"')
    block += [f"{k} = {_toml_value(v)}" for k, v in values.items()]
    target.write_text(text + "\n".join(block) + "\n", encoding="utf-8")
    try:
        load(root)  # make sure the result is still a valid AIDECL.toml
    except ConfigError as e:
        if old is None:
            target.unlink()
        else:
            target.write_text(old, encoding="utf-8")
        raise UsageError(f"{e}; {FILENAME} was left unchanged")
    print(f"Added an annotation for {', '.join(patterns)} to {target}")
    return 0


# ---------------------------------------------------------------- badge
def _weight(root: Path, path: str, mode: str) -> int:
    if mode == "files":
        return 1
    try:
        data = (root / path).read_bytes()
    except OSError:
        return 0
    if b"\x00" in data[:16384]:
        return 1  # binary files count as one line
    return max(1, data.count(b"\n"))


def percentages(counts: dict) -> dict:
    """Integer percentages that sum to 100 (largest-remainder method)."""
    total = sum(counts.values())
    exact = {k: 100 * v / total for k, v in counts.items()}
    result = {k: math.floor(x) for k, x in exact.items()}
    rest = 100 - sum(result.values())
    for k in sorted(exact, key=lambda k: exact[k] - result[k], reverse=True)[:rest]:
        result[k] += 1
    return result


def badge_json(label: str, counts: Counter, keys: list[str], color: str) -> dict:
    shown = {k: counts[k] for k in keys if counts[k]}
    if not shown:
        return {"schemaVersion": 1, "label": label, "message": "no files", "color": "lightgrey"}
    pct = percentages(shown)
    parts = [f"{k} {pct[k]}%" if pct[k] else f"{k} <1%" for k in shown]
    return {"schemaVersion": 1, "label": label, "message": " · ".join(parts),
            "color": "red" if counts["undeclared"] else color}


def cmd_badge(args) -> int:
    project = _open(args.root)
    gen, ver = Counter(), Counter()
    for r in _results(project):
        w = _weight(project.root, r.path, args.weight)
        gen[_status_level(r, "G")] += w
        ver[_status_level(r, "V")] += w
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.weight == "files" else f" ({args.weight})"
    (out / "aidecl-generation.json").write_text(json.dumps(
        badge_json(f"AI generation{suffix}", gen, [*GENERATION, "undeclared"], "4063D8"), ensure_ascii=False))
    (out / "aidecl-verification.json").write_text(json.dumps(
        badge_json(f"verification{suffix}", ver, [*VERIFICATION, "undeclared"], "389826"), ensure_ascii=False))
    print(f"Wrote {out / 'aidecl-generation.json'} and {out / 'aidecl-verification.json'}")
    return 0


# ---------------------------------------------------------------- main
def _add_values(p: argparse.ArgumentParser, required: bool) -> None:
    p.add_argument("-g", "--generation", choices=list(GENERATION), required=required)
    p.add_argument("-v", "--verification", choices=list(VERIFICATION), required=required)
    p.add_argument("--assisted-by", action="append", metavar="TOOL", help="repeatable")
    p.add_argument("--verified-by", action="append", metavar="MODEL", help="repeatable")
    p.add_argument("--tested-by", action="append", metavar="PERSON", help="repeatable")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aidecl", description="Declare and check AI generation (G0-G3) "
                                     "and verification (V0-V3) levels of the files in a repository.")
    parser.add_argument("--version", action="version", version=f"aidecl {__version__}")
    parser.add_argument("--root", default=".", help="project root containing AIDECL.toml (default: .)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help=f"create {FILENAME}")
    _add_values(p, required=False)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("lint", help="check that every file has a valid declaration")
    p.add_argument("--strict", action="store_true", help="also fail on annotations that match no file")
    p.add_argument("--max-files", type=int, default=10, help="files listed per problem (default 10)")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("report", help="summary of the declarations")
    p.add_argument("--files", action="store_true", help="one line per file")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("annotate", help=f"declare files in {FILENAME} (or inline with --inline)")
    p.add_argument("paths", nargs="+", help="files, directories or glob patterns (quote globs)")
    _add_values(p, required=True)
    p.add_argument("--inline", action="store_true", help="write tag comments into the files instead")
    p.add_argument("--precedence", choices=["closest", "override"])
    p.set_defaults(func=cmd_annotate)

    p = sub.add_parser("badge", help="write shields.io endpoint JSON files")
    p.add_argument("--out", default="badges", help="output directory (default: badges)")
    p.add_argument("--weight", choices=["files", "lines"], default="files")
    p.set_defaults(func=cmd_badge)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except UsageError as e:
        print(f"aidecl {args.command}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
