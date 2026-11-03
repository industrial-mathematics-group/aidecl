# aidecl

**Declare and check how each file was created and verified**, using the Industrial Mathematics Group's AI levels (G0–G3 generation, V0–V3 verification). It works like [REUSE](https://reuse.software) does for licences: a path-based `AIDECL.toml`, optional tags in file headers, and a `lint` command for CI.

It complements the commit trailers used in pull requests:

| | Commit trailers | `AIDECL.toml` |
|---|---|---|
| Describes | each **change** merged into `main` | the **current state** of every file |
| Good for | code developed through pull requests | results, data, notebooks, papers, single-commit uploads |
| Checked by | the *AI declaration* PR check | `aidecl lint` |

The levels are defined in the [AI policy](https://github.com/industrial-mathematics-group/.github/blob/main/.github/CONTRIBUTING.md#ai-assisted-contributions):

| Generation | | Verification | |
|---|---|---|---|
| **G0** | Human | **V0** | Human |
| **G1** | AI-assisted | **V1** | Independent agent, same model |
| **G2** | AI-generated | **V2** | Independent agent, different model |
| **G3** | AI-autonomous | **V3** | Human + independent agent |

## Install

```bash
pip install "aidecl @ git+https://github.com/industrial-mathematics-group/aidecl"
# or, without touching your environment:
pipx install "git+https://github.com/industrial-mathematics-group/aidecl"
```

Requires Python 3.11 or newer; no other dependencies.

## Quick start

```bash
# 1. A default for everything (here: written and tested by a human)
aidecl init -g G0 -v V0 --tested-by "Jane Doe"

# 2. Declare what is different, by file, folder or glob
aidecl annotate results/ -g G2 -v V0 --assisted-by "Claude Opus 5.5 (Anthropic)" --tested-by "Jane Doe"
aidecl annotate "scripts/*.jl" -g G1 -v V3 --assisted-by "GitHub Copilot" \
    --verified-by "GPT-5 (OpenAI), independent session" --tested-by "Jane Doe"

# 3. Check that every file is declared correctly
aidecl lint
```

`annotate` refuses incomplete declarations, e.g. G2 without `--assisted-by`, so nothing invalid ends up in the file. It also checks that the resulting `AIDECL.toml` is still valid, and leaves it unchanged if not. Paths are handled like this:
- **Files and folders:** existing files are matched exactly, even with `*` or `?` in their name, and a folder becomes `folder/**`.
- **Globs:** quote them, e.g. `"scripts/*.jl"`. Inside the project they're read relative to the current directory, as the shell would; with `--root` from outside, relative to the root. Globs with `..` or absolute paths are refused.

## AIDECL.toml

```toml
version = 1
exclude = ["docs/build/**"]              # optional: files that need no declaration

[[annotations]]
path = "**"
AI-Generation = "G0"
AI-Verification = "V0"
Tested-by = "Jane Doe"

[[annotations]]
path = ["results/**", "figures/*.pdf"]
AI-Generation = "G2"
AI-Verification = "V3"
Assisted-by = ["Claude Opus 5.5 (Anthropic)"]
Verified-by = "GPT-5 (OpenAI), independent session"
Tested-by = "Jane Doe"
```

- **`path`**: one glob or a list, relative to the repository root. `*` stays within a folder, `**` crosses folders (`**/` also matches no folder), `?` is one character, and `\*`, `\?`, `\\` match those characters literally. This is modelled on `REUSE.toml`, plus `?`.
- **The last matching annotation wins**, so put the general default first and the exceptions after it.
- **Keys** are the same as the commit trailers. `Assisted-by`, `Verified-by` and `Tested-by` take a string or a list.
- **Every file needs a valid declaration:**

| Key | Required for |
|---|---|
| `AI-Generation` | every file |
| `AI-Verification` | every file |
| `Assisted-by` | G1–G3 (and not allowed for G0) |
| `Verified-by` | V1–V3 |
| `Tested-by` | V0 and V3 |

- **Which files are checked:** in a git repository, all tracked files plus untracked files that aren't ignored, so `.gitignore` is respected. If git can't be run in a repository, aidecl stops with an error rather than ignoring `.gitignore`. Outside git, every file below the root is checked. `AIDECL.toml` itself and anything under `exclude` are skipped.

## Inline tags

Source files and documents can also carry the declaration in a comment within their first 30 lines:

```julia
# AI-Generation: G2
# AI-Verification: V1
# Assisted-by: Claude Opus 5.5 (Anthropic)
# Verified-by: Claude Opus 5.5 (Anthropic), fresh review session
```

Three rules keep documentation from being mistaken for a declaration:

- **The file type's own comment syntax:** `#` in Julia, Python or YAML; `//` or `/* */` in C-like languages; `%` in LaTeX; `<!-- -->` in Markdown and HTML. Fenced code blocks in Markdown are skipped. File types without a known comment syntax, such as `.txt`, `.csv`, `.json`, notebooks or `LICENSE`, are only declared through `AIDECL.toml`.
- **Start of the line:** the comment must start the line. Only `*` continuation lines of a `/* */` comment may be indented. Indented examples in docstrings are therefore ignored.
- **A contiguous block with a valid level:** tag lines count only as a block of adjacent lines that contains a valid `AI-Generation: G0`–`G3` or `AI-Verification: V0`–`V3` line. A comment that merely explains the keys, such as `#   AI-Generation: G0-G3`, is ignored.

`aidecl annotate FILE … --inline` writes or updates these lines for you. It places them after a shebang, an encoding line, an XML declaration or (in Markdown) YAML front matter, and leaves everything else in the file untouched, including line endings and a byte-order mark. It reads the result back and restores the file if the tags couldn't be read.

**Precedence:** a file's inline tags win over `AIDECL.toml` ("closest"), unless the matching annotation sets `precedence = "override"`. This works per axis:
- **Generation** (`AI-Generation` with `Assisted-by`) and **verification** (`AI-Verification` with `Verified-by` and `Tested-by`) are separate axes.
- If the inline block only declares one of them, the other comes from the matching annotation in `AIDECL.toml`.
- An axis counts as declared inline when its level line is present.

## Commands

| Command | What it does |
|---|---|
| `aidecl init [-g G -v V …]` | Create `AIDECL.toml`, optionally with a default for all files |
| `aidecl annotate PATHS -g G -v V [--assisted-by …] [--verified-by …] [--tested-by …]` | Append an annotation (`--inline`: tag the files themselves) |
| `aidecl lint [--strict]` | Fail if any file lacks a valid declaration, or if no files were found (`--strict`: also on annotations that match nothing) |
| `aidecl report [--files] [--json]` | Summary per level, one line per file (with the problems), or JSON; invalid declarations count as "undeclared", as in the badges |
| `aidecl badge [--out DIR] [--weight files\|lines]` | Write shields.io endpoint badges `aidecl-generation.json` and `aidecl-verification.json` |

Use `--root DIR` before the command to run on another directory, e.g. `aidecl --root ../paper lint`.

## In CI

The organisation provides a ready-made workflow (*Actions → New workflow → AI file declarations*). It runs `aidecl lint` on every push and pull request and publishes the badges to the `badges` branch:

```markdown
![AI generation](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/<repo>/badges/aidecl-generation.json)
![Verification](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/industrial-mathematics-group/<repo>/badges/aidecl-verification.json)
```

The badges turn red and show an "undeclared" share while files are missing a valid declaration.

## Development

```bash
pip install -e . pytest
pytest
aidecl lint      # the tool declares its own files, too
```

Exit codes: `0` success, `1` problems found by `lint`, `2` usage or configuration errors.
