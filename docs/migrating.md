# Migrating

`aisignoff migrate` handles both the rename from aidecl and older versions of the file format. It converts `SIGNOFF.toml` and the inline tags all or nothing. Run it with `--dry-run` first to see what would change.

## From aidecl

aidecl (up to version 0.3.0) was renamed to aisignoff. The command is now `aisignoff`, and `AIDECL.toml` is now `SIGNOFF.toml`. Keys, levels and inline tags are the same.

1. **Reinstall:** `pipx uninstall aidecl && pipx install aisignoff`.
2. **Rename the file:** `aisignoff migrate` renames `AIDECL.toml` to `SIGNOFF.toml` and keeps its content. If it still uses format version 1 or 2, it's converted in the same step. Commit both sides of the rename: `git add -A SIGNOFF.toml AIDECL.toml`.
3. **Update the badges:** they're now called `aisignoff-generation.json`, `aisignoff-human-review.json` and `aisignoff-ai-review.json` (see [Badges](ci.md#badges)).

Until you migrate, aisignoff still reads `AIDECL.toml` and prints a warning. Having both files is an error.

## From format version 2

Version 2 had the AI review scale A-, A0–A3. The scale moved up by one, so only `AI-Review` (and `ai` in `[policy]`) changes. Comments and layout of `SIGNOFF.toml` are kept.

| Old | New |
|---|---|
| A- (none) | A0 |
| A0 (self-check) | A1; for G0 a TODO, since human-written content has no self-check |
| A1 (independent session) | A2 |
| A2 (different model) | A2, with a note: raise it to A3 if the review was extensive or benchmarked |
| A3 (different model with benchmark) | A3 |

**Repositories with inline tags only:** without `SIGNOFF.toml`, aisignoff can't tell which scale the inline tags use. Run `aisignoff migrate --from 2`; `migrate` points this out when it finds `AI-Review: A-`. It converts the tags and creates a version-3 `SIGNOFF.toml` without annotations. That file records that the tags are converted, so they're never shifted twice. Once `SIGNOFF.toml` is version 3, `--from 2` is refused.

## From format version 1

Version 1 had one verification axis, V0–V3:

| Old | New |
|---|---|
| V0 (human, line by line) | H2, and A0 for G0 |
| V1 / V2 (independent agent, same / different model) | A2 |
| V3 (human + independent agent) | H2 + A2 |
| `Tested-by` | `Reviewed-by` |
| `Verified-by` | `AI-Reviewed-by` |

Comments in `SIGNOFF.toml` are not carried over from version 1.

## TODOs after migrating

What the old levels don't say must be added by a person. Examples are the human review of a V1 file, or the AI review of an AI-written V0 file. `migrate` marks these with a `TODO` comment in `SIGNOFF.toml` and with a `TODO` value in inline tags (e.g. `# Human-Review: TODO`). `lint` reports them until they're filled in.
