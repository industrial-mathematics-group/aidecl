# aisignoff

[![AI generation](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/aisignoff/badges/ai-generation.json)](https://github.com/industrial-mathematics-group/.github/blob/main/.github/CONTRIBUTING.md#g-generation)
[![Human review](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/aisignoff/badges/ai-human-review.json)](https://github.com/industrial-mathematics-group/.github/blob/main/.github/CONTRIBUTING.md#h-human-review)
[![AI review](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/aisignoff/badges/ai-review.json)](https://github.com/industrial-mathematics-group/.github/blob/main/.github/CONTRIBUTING.md#a-ai-review)

![AI generation](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/aisignoff/badges/aisignoff-generation.json)
![Human review](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/aisignoff/badges/aisignoff-human-review.json)
![AI review](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/aisignoff/badges/aisignoff-ai-review.json)

**Declare and check how each file was created and reviewed**, using the Industrial Mathematics Group's AI levels:
- **G0–G3:** how much an AI generated;
- **H0–H3:** how thoroughly a human reviewed it;
- **A0–A3:** how thoroughly an AI reviewed it.

The name is meant both ways: the AI signs off on what it generated or reviewed, and so does the human ("ai", said in German, sounds like "I"). It's a declaration you sign off on, not a cryptographic signature.

It works like [REUSE](https://reuse.software) does for licences: a path-based `SIGNOFF.toml`, optional tags in file headers, and a `lint` command for CI.

It complements the declaration in pull requests, where the levels are ticked in the PR template:

| | PR declaration | `SIGNOFF.toml` |
|---|---|---|
| Describes | each **change** merged into `main` | the **current state** of every file |
| Good for | code developed through pull requests | results, data, notebooks, papers, single-commit uploads |
| Checked by | the *AI declaration* PR check | `aisignoff lint` |

The keys of `SIGNOFF.toml` and the inline tags are the same ones the PR check shows in its job summary.

The levels are defined in the [AI policy](https://github.com/industrial-mathematics-group/.github/blob/main/.github/CONTRIBUTING.md#ai-assisted-contributions):

| Generation | | Human review | | AI review | |
|---|---|---|---|---|---|
| **G0** | Human | **H0** | Plausibility check | **A0** | None |
| **G1** | AI-assisted | **H1** | Tested | **A1** | Self-check by the generating session |
| **G2** | AI-generated | **H2** | Reviewed line by line | **A2** | Review by a new session |
| **G3** | AI-autonomous | **H3** | Independently validated | **A3** | Extensive review or benchmark by a different model |

For human-written content (G0) there is no generating session, so it can't have A1: any AI review of it is A2 or A3.

## Install

```bash
pip install aisignoff
# or, without touching your environment:
pipx install aisignoff      # or: uv tool install aisignoff
```

The latest development version: `pip install "aisignoff @ git+https://github.com/industrial-mathematics-group/aisignoff"`.

Requires Python 3.11 or newer; no other dependencies.

## Quick start

```bash
# 1. A default for everything (here: written by a human, reviewed line by line, no AI review)
aisignoff init -g G0 -H H2 -a A0 --reviewed-by "Jane Doe"

# 2. Declare what is different, by file, folder or glob
aisignoff annotate results/ -g G2 -H H1 -a A1 \
    --assisted-by "Claude Opus 5.5 (Anthropic)" \
    --ai-reviewed-by "Claude Opus 5.5 (Anthropic), same session" --reviewed-by "Jane Doe"
aisignoff annotate "scripts/*.jl" -g G1 -H H3 -a A2 --assisted-by "GitHub Copilot" \
    --ai-reviewed-by "Claude Opus 5.5 (Anthropic), new session" --reviewed-by "Jane Doe"

# 3. Check that every file is declared correctly
aisignoff lint
```

`annotate` refuses incomplete declarations, and anything below the repository's policy (e.g. G2 without `--assisted-by`, or G2 with `-a A0`). It also checks that the resulting `SIGNOFF.toml` is still valid, and leaves it unchanged if not. Paths are handled like this:
- **Inside the project root:** files outside `--root` are refused, also with `--inline`.
- **Files and folders:** existing files are matched exactly, even with `*` or `?` in their name, and a folder becomes `folder/**`.
- **Globs:** quote them, e.g. `"scripts/*.jl"`. Inside the project they're read relative to the current directory, as the shell would; with `--root` from outside, relative to the root. Globs with `..` or absolute paths are refused.

## SIGNOFF.toml

```toml
version = 3
exclude = ["reviews/**", "docs/build/**"]   # optional: files that need no declaration

[policy]                                 # optional: minimum levels
"*" = { human = "H1" }
G3  = { human = "H2", ai = "A2" }

[[annotations]]
path = "**"
AI-Generation = "G0"
Human-Review = "H2"
AI-Review = "A0"
Reviewed-by = "Jane Doe"

[[annotations]]
path = ["results/**", "figures/*.pdf"]
AI-Generation = "G2"
Human-Review = "H3"
AI-Review = "A3"
Assisted-by = ["Claude Opus 5.5 (Anthropic)"]
AI-Reviewed-by = "GPT-5 (OpenAI), full benchmark against reference solutions"
Reviewed-by = "Jane Doe"
```

- **`path`**: one glob or a list, relative to the repository root.
  - `*` stays within a folder, `**` crosses folders (`**/` also matches no folder), and `?` is one character.
  - `\*`, `\?` and `\\` match those characters literally.
  - This is modelled on `REUSE.toml`, plus `?`.
- **The last matching annotation wins**, so put the general default first and the exceptions after it.
- **Keys:** the levels and the names below. `Assisted-by`, `AI-Reviewed-by` and `Reviewed-by` take a string or a list.
- **Every file needs a valid declaration:**

| Key | Required for |
|---|---|
| `AI-Generation`, `Human-Review`, `AI-Review` | every file |
| `Reviewed-by` (the responsible human) | every file |
| `Assisted-by` | G1–G3; not allowed for G0 |
| `AI-Reviewed-by` | A1–A3; not allowed for A0 |

- **Placeholders:** any value may be `"TODO"`, e.g. `Human-Review = "TODO"` when an agent declares its part and a person adds the human review later. `annotate` accepts it too: `-H TODO` without `--reviewed-by` also writes `Reviewed-by` as TODO, so the person fills in both together. It still checks the axes that are filled in. `lint` reports every TODO until it's filled in.
- **Minimum levels:** G1–G3 always need at least **A1**: AI-written content must at least be self-checked. The `[policy]` table can require more (for G0, a minimum of A1 means A2):
  - `"*"` sets the default for every generation level;
  - `G0`–`G3` refine it per generation level, overriding the `"*"` values key by key.
- **Which files are checked:**
  - **In a git repository:** all tracked files plus untracked files that aren't ignored, so `.gitignore` is respected. If git can't be run there, aisignoff stops with an error rather than ignoring `.gitignore`.
  - **Outside git:** every file below the root.
  - **Always skipped:** `SIGNOFF.toml` itself (and `AIDECL.toml`, its old name) and anything under `exclude`. Exclude the folder of committed AI reviews (`reviews/` by default, see CONTRIBUTING.md), since the reviews themselves need no declaration.

## Inline tags

Source files and documents can also carry the declaration in a comment within their first 30 lines:

```julia
# AI-Generation: G2
# Human-Review: H2
# AI-Review: A2
# Assisted-by: Claude Opus 5.5 (Anthropic)
# AI-Reviewed-by: Claude Opus 5.5 (Anthropic), fresh review session
# Reviewed-by: Jane Doe
```

Three rules keep documentation from being mistaken for a declaration:

- **The file type's own comment syntax:**
  - `#` in Julia, Python or YAML;
  - `//` or `/* */` in C-like languages;
  - `%` in LaTeX;
  - `<!-- -->` in Markdown and HTML.

  Fenced code blocks in Markdown are skipped. File types without a known comment syntax, such as `.txt`, `.csv`, `.json`, notebooks or `LICENSE`, are only declared through `SIGNOFF.toml`.
- **Start of the line:** the comment must start the line. Only `*` continuation lines of a `/* */` comment may be indented, so indented examples in docstrings are ignored.
- **A contiguous block with a valid level:** tag lines count only as a block of adjacent lines that contains a valid level line, such as `AI-Generation: G2` or `AI-Review: A0`. A comment that merely explains the keys, like `#   AI-Generation: G0-G3`, is ignored. `TODO` (a placeholder, e.g. left by `aisignoff migrate` or an agent) also counts as a level here, so a block with an unfilled TODO is found and fails `lint`.

`aisignoff annotate FILE … --inline` writes or updates these lines for you:
- **Placement:** after a shebang, an encoding line, an XML declaration or (in Markdown) YAML front matter.
- **The rest of the file stays untouched,** including line endings and a byte-order mark.
- **Safety:** it refuses if the block wouldn't fit into the first 30 lines. It reads the result back and restores the file if the tags couldn't be read.

**Precedence:** a file's inline tags win over `SIGNOFF.toml` ("closest"), unless the matching annotation sets `precedence = "override"`. This works per axis:
- **The axes** are generation (`AI-Generation` with `Assisted-by`), human review (`Human-Review` with `Reviewed-by`) and AI review (`AI-Review` with `AI-Reviewed-by`).
- **An axis counts as declared inline** when its level line is present. Any axis the inline block leaves out comes from the matching annotation.
- **A name line on its own,** such as `Assisted-by` without `AI-Generation`, is an error.

## Commands

| Command | What it does |
|---|---|
| `aisignoff init [-g G -H H -a A …]` | Create `SIGNOFF.toml`, optionally with a default for all files |
| `aisignoff annotate PATHS -g G -H H -a A [--assisted-by …] [--ai-reviewed-by …] --reviewed-by …` | Append an annotation (`--inline`: tag the files themselves) |
| `aisignoff lint [--strict]` | Fail if any file lacks a valid declaration, falls below the policy, or if no files were found (`--strict`: also on annotations that match nothing) |
| `aisignoff report [--files] [--json]` | Summary per axis, one line per file (with the problems), or JSON; invalid declarations count as "undeclared", as in the badges |
| `aisignoff badge [--out DIR] [--weight files\|lines]` | Write shields.io badges `aisignoff-generation.json`, `aisignoff-human-review.json` and `aisignoff-ai-review.json` |
| `aisignoff migrate [--dry-run] [--from 2]` | Convert declarations of earlier versions, see below |

Use `--root DIR` before the command to run on another directory, e.g. `aisignoff --root ../paper lint`.

Exit codes: `0` success, `1` problems found by `lint`, `2` usage or configuration errors.

## Migrating from earlier versions

**From aidecl** (up to version 0.3.0). The tool, its command and its file were renamed: `aidecl` is now `aisignoff`, and `AIDECL.toml` is now `SIGNOFF.toml`. The keys, levels and inline tags stay the same.
- **Reinstall:** `pipx uninstall aidecl && pipx install aisignoff` (or the same with pip).
- **Rename the file:** `aisignoff migrate` renames `AIDECL.toml` to `SIGNOFF.toml` and keeps its content. If the file still uses version 1 or 2, it's converted in the same step, as described below. Commit the rename (`git add -A SIGNOFF.toml AIDECL.toml`).
- **Until then,** aisignoff still reads `AIDECL.toml` and prints a warning. Having both files is an error.
- **Badges** are now called `aisignoff-generation.json`, `aisignoff-human-review.json` and `aisignoff-ai-review.json`; update the URLs in your README (see "In CI" below).

**Between versions of the file format,** `aisignoff migrate` converts `SIGNOFF.toml` and the inline tags to version 3, all or nothing. Without `SIGNOFF.toml`, inline tags with the old AI review scale need `--from 2`; `migrate` points this out when it finds `AI-Review: A-`. `--from 2` then creates a version-3 `SIGNOFF.toml` without annotations, which records that the tags are converted, so they're never shifted twice. Once `SIGNOFF.toml` is version 3, `--from 2` is refused.

**From version 2** (AI review A-, A0–A3). The scale moved up by one, so only `AI-Review` (and `ai` in `[policy]`) changes. Comments and layout of `SIGNOFF.toml` are kept.

| Old | New |
|---|---|
| A- (none) | A0 |
| A0 (self-check) | A1; for G0 a TODO, since human-written content has no self-check |
| A1 (independent session) | A2 |
| A2 (different model) | A2, with a note: raise it to A3 if the review was extensive or benchmarked |
| A3 (different model with benchmark) | A3 |

**From version 1** (one verification axis, V0–V3):

| Old | New |
|---|---|
| V0 (human, line by line) | H2, and A0 for G0 |
| V1 / V2 (independent agent, same / different model) | A2 |
| V3 (human + independent agent) | H2 + A2 |
| `Tested-by` | `Reviewed-by` |
| `Verified-by` | `AI-Reviewed-by` |

What the old levels don't say must be added by a person. Examples are the human review of a V1 file, or the AI review of an AI-written V0 file. `migrate` marks these with a `TODO` comment in `SIGNOFF.toml` and with a `TODO` value in inline tags (e.g. `# Human-Review: TODO`), and `lint` reports them until they're filled in. When converting version 1, comments in `SIGNOFF.toml` are not carried over.

## In CI

The organisation provides a ready-made workflow (*Actions → New workflow → AI file declarations*). It runs `aisignoff lint` on every push and pull request and publishes the badges to the `badges` branch:

```markdown
![AI generation](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/<repo>/badges/aisignoff-generation.json)
![Human review](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/<repo>/badges/aisignoff-human-review.json)
![AI review](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/<repo>/badges/aisignoff-ai-review.json)
```

The badges turn red and show an "undeclared" share while files are missing a valid declaration.

## Development

```bash
pip install -e . pytest
pytest
aisignoff lint      # the tool declares its own files, too (see SIGNOFF.toml)
```

**Releasing:** bump `version` in `pyproject.toml`, `src/aisignoff/__init__.py` and `uv.lock`, then publish a GitHub release with the tag `vX.Y.Z`. The *Publish to PyPI* workflow builds the package and uploads it through PyPI's trusted publishing, so no token is stored in the repository.
