# aidecl

![AI generation](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/aidecl/badges/aidecl-generation.json)
![Human review](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/aidecl/badges/aidecl-human-review.json)
![AI review](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/aidecl/badges/aidecl-ai-review.json)

**Declare and check how each file was created and reviewed**, using the Industrial Mathematics Group's AI levels:
- **G0–G3:** how much an AI generated;
- **H0–H3:** how thoroughly a human reviewed it;
- **A-, A0–A3:** how independently an AI reviewed it.

It works like [REUSE](https://reuse.software) does for licences: a path-based `AIDECL.toml`, optional tags in file headers, and a `lint` command for CI.

It complements the commit trailers used in pull requests:

| | Commit trailers | `AIDECL.toml` |
|---|---|---|
| Describes | each **change** merged into `main` | the **current state** of every file |
| Good for | code developed through pull requests | results, data, notebooks, papers, single-commit uploads |
| Checked by | the *AI declaration* PR check | `aidecl lint` |

The levels are defined in the [AI policy](https://github.com/industrial-mathematics-group/.github/blob/main/.github/CONTRIBUTING.md#ai-assisted-contributions):

| Generation | | Human review | | AI review | |
|---|---|---|---|---|---|
| **G0** | Human | **H0** | Plausibility check | **A-** | None |
| **G1** | AI-assisted | **H1** | Tested | **A0** | Self-check by the generating session |
| **G2** | AI-generated | **H2** | Reviewed line by line | **A1** | Independent session, same model |
| **G3** | AI-autonomous | **H3** | Independently validated | **A2** | Independent session, different model |
| | | | | **A3** | Different model with a full benchmark |

## Install

```bash
pip install "aidecl @ git+https://github.com/industrial-mathematics-group/aidecl"
# or, without touching your environment:
pipx install "git+https://github.com/industrial-mathematics-group/aidecl"
```

Requires Python 3.11 or newer; no other dependencies.

## Quick start

```bash
# 1. A default for everything (here: written by a human, reviewed line by line, no AI review)
aidecl init -g G0 -H H2 -a A- --reviewed-by "Jane Doe"

# 2. Declare what is different, by file, folder or glob
aidecl annotate results/ -g G2 -H H1 -a A0 \
    --assisted-by "Claude Opus 5.5 (Anthropic)" \
    --ai-reviewed-by "Claude Opus 5.5 (Anthropic), same session" --reviewed-by "Jane Doe"
aidecl annotate "scripts/*.jl" -g G1 -H H3 -a A2 --assisted-by "GitHub Copilot" \
    --ai-reviewed-by "GPT-5 (OpenAI), independent session" --reviewed-by "Jane Doe"

# 3. Check that every file is declared correctly
aidecl lint
```

`annotate` refuses incomplete declarations, and anything below the repository's policy (e.g. G2 without `--assisted-by`, or G2 with `-a A-`). It also checks that the resulting `AIDECL.toml` is still valid, and leaves it unchanged if not. Paths are handled like this:
- **Files and folders:** existing files are matched exactly, even with `*` or `?` in their name, and a folder becomes `folder/**`.
- **Globs:** quote them, e.g. `"scripts/*.jl"`. Inside the project they're read relative to the current directory, as the shell would; with `--root` from outside, relative to the root. Globs with `..` or absolute paths are refused.

## AIDECL.toml

```toml
version = 2
exclude = ["docs/build/**"]              # optional: files that need no declaration

[policy]                                 # optional: minimum levels
"*" = { human = "H1" }
G3  = { human = "H2", ai = "A1" }

[[annotations]]
path = "**"
AI-Generation = "G0"
Human-Review = "H2"
AI-Review = "A-"
Reviewed-by = "Jane Doe"

[[annotations]]
path = ["results/**", "figures/*.pdf"]
AI-Generation = "G2"
Human-Review = "H3"
AI-Review = "A2"
Assisted-by = ["Claude Opus 5.5 (Anthropic)"]
AI-Reviewed-by = "GPT-5 (OpenAI), independent session"
Reviewed-by = "Jane Doe"
```

- **`path`**: one glob or a list, relative to the repository root.
  - `*` stays within a folder, `**` crosses folders (`**/` also matches no folder), and `?` is one character.
  - `\*`, `\?` and `\\` match those characters literally.
  - This is modelled on `REUSE.toml`, plus `?`.
- **The last matching annotation wins**, so put the general default first and the exceptions after it.
- **Keys** are the same as the commit trailers. `Assisted-by`, `AI-Reviewed-by` and `Reviewed-by` take a string or a list.
- **Every file needs a valid declaration:**

| Key | Required for |
|---|---|
| `AI-Generation`, `Human-Review`, `AI-Review` | every file |
| `Reviewed-by` (the responsible human) | every file |
| `Assisted-by` | G1–G3; not allowed for G0 |
| `AI-Reviewed-by` | A0–A3; not allowed for A- |

- **Minimum levels:** G1–G3 always need at least **A0**: AI-written content must at least be self-checked. The `[policy]` table can require more:
  - `"*"` sets the default for every generation level;
  - `G0`–`G3` refine it per generation level, overriding the `"*"` values key by key.
- **Which files are checked:**
  - **In a git repository:** all tracked files plus untracked files that aren't ignored, so `.gitignore` is respected. If git can't be run there, aidecl stops with an error rather than ignoring `.gitignore`.
  - **Outside git:** every file below the root.
  - **Always skipped:** `AIDECL.toml` itself and anything under `exclude`.

## Inline tags

Source files and documents can also carry the declaration in a comment within their first 30 lines:

```julia
# AI-Generation: G2
# Human-Review: H2
# AI-Review: A1
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

  Fenced code blocks in Markdown are skipped. File types without a known comment syntax, such as `.txt`, `.csv`, `.json`, notebooks or `LICENSE`, are only declared through `AIDECL.toml`.
- **Start of the line:** the comment must start the line. Only `*` continuation lines of a `/* */` comment may be indented, so indented examples in docstrings are ignored.
- **A contiguous block with a valid level:** tag lines count only as a block of adjacent lines that contains a valid level line, such as `AI-Generation: G2` or `AI-Review: A-`. A comment that merely explains the keys, like `#   AI-Generation: G0-G3`, is ignored. `TODO` (left by `aidecl migrate`) also counts as a level here, so a block with an unfilled TODO is found and fails `lint`.

`aidecl annotate FILE … --inline` writes or updates these lines for you:
- **Placement:** after a shebang, an encoding line, an XML declaration or (in Markdown) YAML front matter.
- **The rest of the file stays untouched,** including line endings and a byte-order mark.
- **Safety:** it refuses if the block wouldn't fit into the first 30 lines. It reads the result back and restores the file if the tags couldn't be read.

**Precedence:** a file's inline tags win over `AIDECL.toml` ("closest"), unless the matching annotation sets `precedence = "override"`. This works per axis:
- **The axes** are generation (`AI-Generation` with `Assisted-by`), human review (`Human-Review` with `Reviewed-by`) and AI review (`AI-Review` with `AI-Reviewed-by`).
- **An axis counts as declared inline** when its level line is present. Any axis the inline block leaves out comes from the matching annotation.
- **A name line on its own,** such as `Assisted-by` without `AI-Generation`, is an error.

## Commands

| Command | What it does |
|---|---|
| `aidecl init [-g G -H H -a A …]` | Create `AIDECL.toml`, optionally with a default for all files |
| `aidecl annotate PATHS -g G -H H -a A [--assisted-by …] [--ai-reviewed-by …] --reviewed-by …` | Append an annotation (`--inline`: tag the files themselves) |
| `aidecl lint [--strict]` | Fail if any file lacks a valid declaration, falls below the policy, or if no files were found (`--strict`: also on annotations that match nothing) |
| `aidecl report [--files] [--json]` | Summary per axis, one line per file (with the problems), or JSON; invalid declarations count as "undeclared", as in the badges |
| `aidecl badge [--out DIR] [--weight files\|lines]` | Write shields.io badges `aidecl-generation.json`, `aidecl-human-review.json` and `aidecl-ai-review.json` |
| `aidecl migrate [--dry-run]` | Convert declarations of the first version (V0–V3) to G/H/A, see below |

Use `--root DIR` before the command to run on another directory, e.g. `aidecl --root ../paper lint`.

Exit codes: `0` success, `1` problems found by `lint`, `2` usage or configuration errors.

## Migrating from V0–V3

The first version used one verification axis, V0–V3. `aidecl migrate` rewrites `AIDECL.toml` (version 1 → 2) and inline tags, mapping:

| Old | New |
|---|---|
| V0 (human, line by line) | H2, and A- for G0 |
| V1 / V2 (independent agent, same / different model) | A1 / A2 |
| V3 (human + independent agent) | H2 + A1 |
| `Tested-by` | `Reviewed-by` |
| `Verified-by` | `AI-Reviewed-by` |

What the old levels don't say must be added by a person. Examples are the human review of a V1 file, or the AI review of an AI-written V0 file. `migrate` marks these with a `TODO` comment in `AIDECL.toml` and with a `TODO` value in inline tags (e.g. `# Human-Review: TODO`), and `lint` reports them until they're filled in. Comments in the old `AIDECL.toml` are not carried over.

## In CI

The organisation provides a ready-made workflow (*Actions → New workflow → AI file declarations*). It runs `aidecl lint` on every push and pull request and publishes the badges to the `badges` branch:

```markdown
![AI generation](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/<repo>/badges/aidecl-generation.json)
![Human review](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/<repo>/badges/aidecl-human-review.json)
![AI review](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/<repo>/badges/aidecl-ai-review.json)
```

The badges turn red and show an "undeclared" share while files are missing a valid declaration.

## Development

```bash
pip install -e . pytest
pytest
aidecl lint      # the tool declares its own files, too (see AIDECL.toml)
```
