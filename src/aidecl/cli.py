"""Command-line interface: aidecl init | lint | report | annotate | badge | migrate."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import __version__, inline
from .config import FILENAME, VERSION, ConfigError, LegacyConfig, load, read_toml
from .globbing import escape
from .model import (AI, AI_REVIEWED, AIR, ASSISTED, GEN, GENERATION, HUM, HUMAN, KEYS, LIST_KEYS, REVIEWED,
                    TODO, Declaration, Policy, canonical_key, validate)
from .project import Project, ProjectError, list_files

SPEC_URL = ("https://github.com/industrial-mathematics-group/.github/blob/main/.github/"
            "CONTRIBUTING.md#ai-assisted-contributions")
AXIS_INFO = (  # key, short, title, levels, badge file, colour
    (GEN, "G", "Generation", GENERATION, "aidecl-generation.json", "4063D8"),
    (HUM, "H", "Human review", HUMAN, "aidecl-human-review.json", "389826"),
    (AIR, "A", "AI review", AI, "aidecl-ai-review.json", "9558B2"),
)


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
    values = {GEN: args.generation, HUM: args.human, AIR: args.ai}
    for key, items in ((ASSISTED, args.assisted_by), (REVIEWED, args.reviewed_by),
                       (AI_REVIEWED, args.ai_reviewed_by)):
        if items:
            for item in items:
                if not item.strip() or any(ord(c) < 32 or ord(c) == 127 for c in item):
                    raise UsageError(f"{key} values must be non-empty single-line text: {item!r}")
            values[key] = [i.strip() for i in items]
    return {k: v for k, v in values.items() if v}


def _policy(root: Path) -> Policy:
    try:
        return load(root).policy
    except ConfigError as e:
        raise UsageError(str(e))


def _check_complete(values: dict, policy: Policy) -> None:
    problems = validate(Declaration.from_mapping(values, source="command line"), policy)
    if problems:
        raise UsageError("incomplete declaration: " + "; ".join(problems))


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


def _status_level(r, key: str) -> str:
    """Level for counting: the declared level if the declaration is valid, else 'undeclared'."""
    return "undeclared" if r.errors else r.declaration.get(key)


# ---------------------------------------------------------------- init
def cmd_init(args) -> int:
    root = Path(args.root)
    if not root.is_dir():
        raise UsageError(f"project root {root} is not a directory")
    target = root / FILENAME
    if target.exists():
        raise UsageError(f"{target} already exists")
    lines = [
        "# AI declarations for this repository: generation (G0-G3), human review (H0-H3)",
        "# and AI review (A-, A0-A3).",
        f"# Scheme: {SPEC_URL}",
        "# The LAST annotation that matches a file wins. Inline tags in a file win over",
        '# this file unless the matching annotation sets precedence = "override".',
        f"version = {VERSION}",
        "",
        '# exclude = ["docs/build/**"]   # files that need no declaration',
        "",
        "# Minimum review levels (optional). G1-G3 always need at least A0.",
        "# [policy]",
        '# "*" = { human = "H1" }',
        '# G3  = { human = "H2", ai = "A1" }',
        "",
    ]
    given = [args.generation, args.human, args.ai]
    if any(given):
        if not all(given):
            raise UsageError("give --generation, --human and --ai together, or none of them")
        values = _values(args)
        _check_complete(values, Policy())
        lines += ["# Default for everything", "[[annotations]]", 'path = "**"']
        lines += [f"{k} = {_toml_value(v)}" for k, v in values.items()]
    else:
        lines += [
            "# Example:",
            "# [[annotations]]",
            '# path = "**"',
            '# AI-Generation = "G0"',
            '# Human-Review = "H2"',
            '# AI-Review = "A-"',
            '# Reviewed-by = "Jane Doe"',
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
            status = "✓" if not r.errors else "✗"
            line = f"{status} {r.path:<{width}}  {r.declaration.short()}  ({r.declaration.source})"
            if r.errors:
                line += "  " + "; ".join(r.errors)
            print(line)
        return 0
    total = len(results) or 1
    print(f"{len(results)} files\n")
    for key, _, title, levels, _, _ in AXIS_INFO:
        counts = Counter(_status_level(r, key) for r in results)
        print(title)
        for level, name in list(levels.items()) + [("undeclared", "missing or invalid declaration")]:
            if counts[level]:
                print(f"  {level:<10} {name:<38} {counts[level]:>5}  {100 * counts[level] / total:5.1f}%")
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


def _append_annotation(root: Path, patterns: list[str], values: dict, precedence: str | None,
                       comments: list[str] = ()) -> None:
    target = root / FILENAME
    old = target.read_text(encoding="utf-8") if target.exists() else None
    text = old if old is not None else f"version = {VERSION}\n"
    if not text.endswith("\n"):
        text += "\n"
    block = ["", *[f"# {c}" for c in comments], "[[annotations]]",
             f"path = {_toml_value(patterns[0] if len(patterns) == 1 else patterns)}"]
    if precedence:
        block.append(f'precedence = "{precedence}"')
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


def cmd_annotate(args) -> int:
    root = Path(args.root)
    if not root.is_dir():
        raise UsageError(f"project root {root} is not a directory")
    values = _values(args)
    _check_complete(values, _policy(root))

    if args.inline:
        if args.precedence:
            raise UsageError("--precedence only applies to AIDECL.toml, not to --inline")
        status = 0
        for arg in args.paths:
            path = Path(arg)
            if not path.is_file():
                print(f"aidecl annotate: {arg} does not exist or is not a file", file=sys.stderr)
                status = 1
                continue
            try:
                inline.write(path, values)
                print(f"Tagged {path}")
            except (ValueError, OSError, UnicodeDecodeError) as e:
                print(f"aidecl annotate: {e}", file=sys.stderr)
                status = 1
        return status

    patterns = [_pattern(root, a) for a in args.paths]
    _append_annotation(root, patterns, values, args.precedence)
    print(f"Added an annotation for {', '.join(patterns)} to {root / FILENAME}")
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
    results = _results(project)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.weight == "files" else f" ({args.weight})"
    weights = {r.path: _weight(project.root, r.path, args.weight) for r in results}
    written = []
    for key, _, title, levels, filename, color in AXIS_INFO:
        counts = Counter()
        for r in results:
            counts[_status_level(r, key)] += weights[r.path]
        label = {GEN: "AI generation", HUM: "human review", AIR: "AI review"}[key] + suffix
        (out / filename).write_text(json.dumps(badge_json(label, counts, [*levels, "undeclared"], color),
                                               ensure_ascii=False))
        written.append(str(out / filename))
    print("Wrote " + ", ".join(written))
    return 0


# ---------------------------------------------------------------- migrate
def migrate_values(old: dict) -> tuple[dict, list[str]]:
    """Map a version-1 declaration (V0-V3) to G/H/A. Returns (values, keys a human must add).

    V0 (human ran the tests and reviewed line by line) -> H2, AI review unknown (A- for G0)
    V1 / V2 (independent agent, same / different model)  -> A1 / A2, human review unknown
    V3 (human + independent agent)                       -> H2 + A1 (the model is not recorded)
    """
    get = {canonical_key(k, (GEN, ASSISTED, "AI-Verification", "Verified-by", "Tested-by")): v
           for k, v in old.items()}
    values: dict = {}
    if get.get(GEN):
        values[GEN] = get[GEN]
    if get.get(ASSISTED):
        values[ASSISTED] = get[ASSISTED]
    v = get.get("AI-Verification")
    tested, verified = get.get("Tested-by"), get.get("Verified-by")
    if v in ("V0", "V3"):
        values[HUM] = "H2"
        if tested:
            values[REVIEWED] = tested
    if v in ("V1", "V3"):
        values[AIR] = "A1"
    elif v == "V2":
        values[AIR] = "A2"
    elif v == "V0" and values.get(GEN) == "G0":
        values[AIR] = "A-"
    if AIR in values and values[AIR] != "A-" and verified:
        values[AI_REVIEWED] = verified
    todo = [k for k in (GEN, HUM, REVIEWED, AIR) if k not in values]
    if values.get(AIR) not in (None, "A-") and AI_REVIEWED not in values:
        todo.append(AI_REVIEWED)
    return values, todo


def cmd_migrate(args) -> int:
    root = Path(args.root)
    if not root.is_dir():
        raise UsageError(f"project root {root} is not a directory")
    changes = []
    todos = 0

    # AIDECL.toml
    data = None
    try:
        data = read_toml(root)
    except ConfigError as e:
        raise UsageError(str(e))
    new_text = None
    warnings = []
    if data is not None and data.get("version") == 1:
        lines = [
            "# AI declarations (migrated from version 1 by 'aidecl migrate').",
            f"# Scheme: {SPEC_URL}",
            f"version = {VERSION}",
        ]
        if data.get("exclude"):
            lines += ["", f"exclude = {_toml_value(list(data['exclude']))}"]
        old_keys = (GEN, ASSISTED, "AI-Verification", "Verified-by", "Tested-by")
        for i, table in enumerate(data.get("annotations", []), start=1):
            if not isinstance(table, dict) or "path" not in table:
                raise UsageError(f"{FILENAME} annotation [{i}] has no 'path'; fix it, then run migrate again")
            rest = {k: v for k, v in table.items() if k not in ("path", "precedence")}
            for k in rest:
                if canonical_key(k, old_keys) is None:
                    warnings.append(f"{FILENAME} annotation [{i}]: key '{k}' is not part of the scheme and was dropped")
            values, todo = migrate_values(rest)
            todos += bool(todo)
            lines.append("")
            if todo:
                lines.append(f"# TODO after migration: add {', '.join(todo)}")
            lines.append("[[annotations]]")
            lines.append(f"path = {_toml_value(table['path'])}")
            if table.get("precedence"):
                lines.append(f"precedence = {_toml_value(table['precedence'])}")
            lines += [f"{k} = {_toml_value(v)}" for k, v in values.items()]
        new_text = "\n".join(lines) + "\n"
        changes.append(f"{FILENAME}: version 1 -> {VERSION}")

    # inline blocks with the old keys
    inline_updates = []
    try:
        files = list_files(root.resolve())
    except ProjectError as e:
        raise UsageError(str(e))
    for f in files:
        found = inline.parse_values(root / f)
        if found is None or not any(k in found[0] for k in ("AI-Verification", "Verified-by", "Tested-by")):
            continue
        values, todo = migrate_values(found[0])
        todos += bool(todo)
        # explicit TODO markers: an inline axis without its level line would otherwise be
        # filled in from AIDECL.toml, which would claim a review that never happened
        for key in todo:
            values[key] = [TODO] if key in LIST_KEYS else TODO
        values = {k: values[k] for k in KEYS if k in values}
        inline_updates.append((f, values, todo))
        changes.append(f"{f}: inline tags" + (f" (TODO: add {', '.join(todo)})" if todo else ""))

    if not changes:
        print("Nothing to migrate.")
        return 0
    for w in warnings:
        print(f"warning: {w}")
    if args.dry_run:
        for c in changes:
            print("would migrate " + c)
        return 0
    status = 0
    if new_text is not None:
        target = root / FILENAME
        old_text = target.read_text(encoding="utf-8")
        target.write_text(new_text, encoding="utf-8")
        try:
            load(root)
        except ConfigError as e:
            target.write_text(old_text, encoding="utf-8")
            raise UsageError(f"the converted {FILENAME} would be invalid ({e}); fix the old file first. "
                             "Nothing was changed")
    failed = set()
    for f, values, _ in inline_updates:
        try:
            inline.write(root / f, values)
        except (ValueError, OSError, UnicodeDecodeError) as e:
            print(f"aidecl migrate: {e}", file=sys.stderr)
            failed.add(f)
            status = 1
    for c in changes:
        if not any(c.startswith(f"{f}: inline tags") for f in failed):
            print("migrated " + c)
    if todos:
        print("\nSome declarations need information the old levels don't contain (marked TODO).")
        print("'aidecl lint' fails until they are filled in.")
    return status


# ---------------------------------------------------------------- main
def _add_values(p: argparse.ArgumentParser, required: bool) -> None:
    p.add_argument("-g", "--generation", choices=list(GENERATION), required=required)
    p.add_argument("-H", "--human", choices=list(HUMAN), required=required, help="human review level")
    p.add_argument("-a", "--ai", choices=list(AI), required=required, help="AI review level")
    p.add_argument("--assisted-by", action="append", metavar="TOOL", help="repeatable (G1-G3)")
    p.add_argument("--reviewed-by", action="append", metavar="PERSON",
                   help="repeatable; the responsible human (always required)")
    p.add_argument("--ai-reviewed-by", action="append", metavar="MODEL", help="repeatable (A0-A3)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aidecl", description="Declare and check AI generation (G0-G3), "
                                     "human review (H0-H3) and AI review (A-, A0-A3) of the files in a repository.")
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

    p = sub.add_parser("migrate", help="convert version-1 declarations (V0-V3) to G/H/A")
    p.add_argument("--dry-run", action="store_true", help="only show what would change")
    p.set_defaults(func=cmd_migrate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except UsageError as e:
        print(f"aidecl {args.command}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
