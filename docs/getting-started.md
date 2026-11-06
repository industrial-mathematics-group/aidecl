# Getting started

## Install

```bash
pipx install aisignoff        # or: uv tool install aisignoff, or: pip install aisignoff
```

aisignoff needs Python 3.11 or newer and has no other dependencies. For the latest development version:

```bash
pipx install "git+https://github.com/industrial-mathematics-group/aisignoff"
```

## Declare a repository

Run these in the repository root.

**1. Set a default for everything.** Here: written by a human, reviewed line by line, no AI review.

```bash
aisignoff init -g G0 -H H2 -a A0 --reviewed-by "Jane Doe"
```

This creates [`SIGNOFF.toml`](signoff-toml.md) with one annotation for `**`.

**2. Declare what is different,** by file, folder or glob:

```bash
aisignoff annotate results/ -g G2 -H H1 -a A1 \
    --assisted-by "Claude Opus 5.5 (Anthropic)" \
    --ai-reviewed-by "Claude Opus 5.5 (Anthropic), same session" \
    --reviewed-by "Jane Doe"

aisignoff annotate "scripts/*.jl" -g G1 -H H3 -a A2 \
    --assisted-by "GitHub Copilot" \
    --ai-reviewed-by "Claude Opus 5.5 (Anthropic), new session" \
    --reviewed-by "Jane Doe"
```

Each call appends an annotation. The last matching one wins, so later, more specific annotations override the default.

**3. Check that every file is declared correctly:**

```bash
aisignoff lint
aisignoff report --files      # one line per file, with where its declaration comes from
```

Add the check to [CI](ci.md) so it stays that way.

## What `annotate` checks

`annotate` refuses incomplete declarations and anything below the repository's [policy](signoff-toml.md#minimum-levels). Examples are G2 without `--assisted-by`, or G2 with `-a A0`. It also checks that the resulting `SIGNOFF.toml` is still valid, and leaves it unchanged if not.

Paths are handled like this:

- **Inside the project root:** files outside `--root` are refused, also with `--inline`.
- **Files and folders:** existing files are matched exactly, even with `*` or `?` in their name. A folder becomes `folder/**`.
- **Globs:** quote them, e.g. `"scripts/*.jl"`.
    - Inside the project, they're read relative to the current directory, as the shell would.
    - With `--root` from outside the project, they're relative to the root.
    - Globs with `..` or absolute paths are refused.

## Leaving the human review open

When an AI agent declares its own work, the human review isn't done yet. Use `TODO`:

```bash
aisignoff annotate src/solver.py -g G3 -H TODO -a A1 \
    --assisted-by "Claude Opus 5.5 (Anthropic)" \
    --ai-reviewed-by "Claude Opus 5.5 (Anthropic), self-check by the generating session"
```

`-H TODO` without `--reviewed-by` writes `Reviewed-by` as TODO too, so the person fills in both together. `lint` fails until they do.

## Declaring inside files

Text files can carry their declaration in a header comment instead:

```bash
aisignoff annotate analysis.py --inline -g G2 -H H1 -a A1 \
    --assisted-by "Claude Opus 5.5 (Anthropic)" \
    --ai-reviewed-by "Claude Opus 5.5 (Anthropic), same session" \
    --reviewed-by "Jane Doe"
```

See [Inline tags](inline-tags.md) for the rules.
