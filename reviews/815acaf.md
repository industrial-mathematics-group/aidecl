# Reviews of 815acaf ("Updated AI verification tiers")

Two independent AI reviews (A2) of commit `815acaf`, each by a fresh Claude Opus 5.5 (Anthropic) session without the conversation that generated the change. The reviewers worked separately and both ran the test suite. Their findings are addressed in the follow-up pull request that adds this file.

## Review of aidecl after the tier change (reviewer A)

- **Repository:** industrial-mathematics-group/aidecl, `main` at `815acaf` ("Updated AI verification tiers")
- **Compared against:** org `CONTRIBUTING.md` (AI-assisted contributions), org PR template, org workflows `ai-declaration.yml` / `aidecl.yml` / `workflow-templates/aidecl.yml` (all on `main` of `industrial-mathematics-group/.github`), and the project instructions' AIDECL summary
- **Reviewer:** Claude Opus 5.5 (Anthropic), a session without the conversation that generated the change
- **Date:** 2026-11-04

### Summary

The tier change is consistent across the code, CLI and docs. The new A0–A3 scale, the rule "G1–G3 need at least A1", the rule "G0 is never A1", and "a policy minimum of A1 means A2 for G0" are applied the same way in `model.py`, the CLI (`init`, `annotate`, `lint`), the README, the org CONTRIBUTING.md, the org PR check and the PR template. `migrate` from version 2 behaves as documented in both the README and CONTRIBUTING.md (including the G0 + old A0 → TODO case, the A2 note, policy conversion, keeping comments and CRLF, and refusing a second `--from 2`).

**Tests:** `pytest -q`: 118 passed on Python 3.11, 3.12 and 3.13. `aidecl lint` on the repo itself: 16 of 16 files valid.

I found no correctness bug in the scale logic. What's left is one stale string, a few gaps where the docs promise something the CLI doesn't do, and two points about the repo's own declaration.

### Findings

#### Should fix

1. **`pyproject.toml` description still shows the old scale.** Line 8 says "AI review (A-, A0-A3)". `__init__.py`, the README and the CLI help were updated; this is the one place that was missed. It shows up on the package metadata (`pip show aidecl`).

2. **The repo's own declaration claims A2, but no review is committed.** `AIDECL.toml` declares `AI-Review = "A2"` for `**`, and CONTRIBUTING.md now says A2/A3 reviews must be committed under `reviews/` (`commit#.md` / `pull#.md`). The repo has no `reviews/` folder. Either commit the review (this file could be the start of one) and add `exclude = ["reviews/**"]`, or declare A1 until then. Whether a fresh-session review of the *final* change happened is Pascal's call; I can't tell from the history.

3. **`TODO` is documented as a general placeholder, but the CLI can't write it and the message still blames `migrate`.**
   - README: "any value may be `"TODO"`, e.g. `Human-Review = "TODO"` when an agent declares its part and a person adds the human review later."
   - `aidecl annotate … -H TODO` is rejected by argparse (`choices` are only H0–H3), so an agent following the project rule "use TODO until Pascal sets it" has to hand-edit `AIDECL.toml` or the header.
   - `lint` reports it as "Human-Review is still TODO (left by 'aidecl migrate')" (`model.py:165`), which is misleading when the TODO was placed on purpose.
   - Suggested fix: accept `TODO` in `-g/-H/-a` (and skip the "needs Reviewed-by" check for that axis, which `validate` already does), and change the message to "… is still TODO (to be filled in by a person)".

#### Nice to fix

4. **Lint hint loop for inline `A-` in a version-3 repo.** `lint` says "A- is now A0; run 'aidecl migrate'", but in a repo whose `AIDECL.toml` is already version 3, `migrate` answers "convert the old tags in these files by hand". The hint should depend on the situation, or just say "use A0".

5. **`A-` inside a version-3 `AIDECL.toml` gets no hint.** `config.py:345` raises "invalid AI-Review 'A-' (use A0, A1, A2, A3)" without the "A- is now A0" hint that `parse_policy` and inline `validate` give. Easy to make consistent.

6. **The `reviews/` convention isn't reflected in the tool.** CONTRIBUTING.md says the review folder should be excluded from the declaration, but neither `aidecl init` (its template comment shows `exclude = ["docs/build/**"]`) nor the README mentions `reviews/**`. Adding `exclude = ["reviews/**"]` to the `init` output (commented or active) and one line to the README would make the rule hard to miss.

7. **`aidecl-ref: v0.3.0` points to a tag that doesn't exist.** Both this repo's `.github/workflows/aidecl.yml` and the org `workflow-templates/aidecl.yml` suggest pinning `v0.3.0` (before: `v0.2.0`), but the repo has no tags at all. Tag `v0.3.0` on `815acaf`, or drop the example.

8. **Naming of the model in the repo's own `AIDECL.toml`.** It uses `"Claude (Anthropic), claude-opus-5-5"`, while CONTRIBUTING.md, the README and the project rules use "Claude Opus 5.5 (Anthropic)". Not checked by the tool; cosmetic.

#### Nits

9. `model.py:72` (comment) and `model.py:97` (error message) use `ai = "A0"` as the policy example. A0 as a minimum is a no-op on the new scale; `"A2"` would be a more meaningful example.
10. The tool's report label for A0 is "No AI review"; CONTRIBUTING calls it "None", and for H2 "Reviewed" vs the tool's "Reviewed line by line". Same meaning, just not word for word.
11. The org PR template's checklist still says "Tests pass locally (`Pkg.test()`)", which is Julia-specific, and aidecl (Python) has no template of its own. Unrelated to the tier change.

### Checked and fine

- `model.py`: AI levels and names; `BUILTIN_MIN_AI_FOR_GENERATED = "A1"`; G0 + A1 is an error; a G0 policy minimum of A1 becomes A2 (also when set explicitly under `G0`); A0 with `AI-Reviewed-by` is an error; A1–A3 require it.
- `config.py`: version 3 required; versions 1 and 2 point to `migrate`; `TODO` allowed as a level.
- CLI: `init -g G0 -a A1` and `annotate -g G2 -a A0` are refused with clear messages; `init` comments updated; `report` and `badge` count TODO declarations as "undeclared".
- `migrate` (v2 → v3): A- → A0, A0 → A1 (G0: TODO with a comment), A1 → A2, A2 → A2 with a note, A3 → A3; quoted and lower-case keys; `[policy]`, `[policy.G2]` and inline-table policies; trailing comments kept; inline tags use the generation from the matching v2 annotation; unusual layouts are refused without changes; a second run and `--from 2` on a v3 repo are refused.
- `migrate` (v1 → v3): V1 and V2 → A2, V3 → H2 + A2, matching CONTRIBUTING.md.
- Org PR check (`ai-declaration.yml`): same rules (G0 never A1, A1 floor for G1–G3, A1 → A2 for G0 policies), reads a v2 base-branch policy on the old scale, rejects `A-` and the old A0 tick.

### The project instructions' AIDECL summary

It matches the repo and CONTRIBUTING.md on all levels and rules. Three small gaps:

- It doesn't mention that **a policy minimum of A1 means A2 for G0**.
- "Inline tags beat AIDECL.toml" is true by default, but an annotation with `precedence = "override"` wins over inline tags, and inline tags only override the axes they set.
- "Use TODO until Pascal sets it" works in `AIDECL.toml` and in headers by hand, but not through `aidecl annotate` (finding 3). In a PR body, `Human-Review: TODO` fails the PR check, which effectively blocks the PR until Pascal fills it in. That is probably the intended effect, but it's worth knowing.

## aidecl review after the tier change (reviewer B)

Reviewed on 2026-11-04 at aidecl `815acaf` ("Updated AI verification tiers") and the org `.github` repo at `39f797a` (includes `41745fc` "Updated AI verification tiers" and the bot-declaration PR #1). This review was written independently of reviewer A.

### Overall verdict

The tier change is applied consistently across the parts that matter. `model.py`, `config.py`, `inline.py` and `cli.py` (lint, annotate, migrate, badges), plus the README, CONTRIBUTING.md, the PR template, the PR check workflow, the badge workflows, SETUP.md and the org profile, all use the same scale:

- A0 is none, A1 is a self-check, A2 is a new session, and A3 is a different model with extensive review or benchmarking.
- G1 to G3 need at least A1.
- G0 can never be A1, and a policy minimum of A1 means A2 for G0.

The v2 to v3 migration table is the same in the code, the README, CONTRIBUTING.md, SETUP.md and both workflows. I found no logic errors in the new rules. All findings below are gaps around the edges.

**Tests:** `pytest -q` gives 118 passed (Python 3.13). `aidecl lint` on the repo itself gives 16 of 16 files valid (G3 · H1 · A2).

I also spot-checked the CLI by hand:

- `annotate -g G0 -a A1` is refused.
- `annotate -g G2 -a A0` is refused.
- Inline `G0/A1` fails lint.
- `[policy] "*" = {ai="A1"}` makes G0 files require A2.
- TODO values fail lint.

### Findings, most important first

1. **The repo's own A2 declaration breaks the new "reviews must be committed" rule.** `AIDECL.toml` declares `AI-Review = "A2"` for `**`, but the repo has no `reviews/` folder and no `reviews/commit#.md` or `pull#.md`. CONTRIBUTING.md (commit `080949f`) now requires one for A2 and A3. Either commit the review file(s), or declare A1 until one exists. When you add `reviews/`, also add `exclude = ["reviews/**"]` to `AIDECL.toml`; otherwise `aidecl lint` will fail on the review files.

2. **No `v0.3.0` tag exists, but the docs suggest pinning it.** `git ls-remote --tags` returns nothing. Two places suggest it: `.github/workflows/aidecl.yml`, in the commented-out `aidecl-ref: v0.3.0` line in both aidecl and the org template, and SETUP.md ("tag a release (e.g. `v0.3.0`)"). Uncommenting the line would break the install step. Meanwhile, every repo that uses the reusable workflow installs aidecl from `main`. So any repo still on `AIDECL.toml` version 2 started failing `aidecl lint` this morning until someone runs `aidecl migrate`. Tag `v0.3.0` (and probably `v0.2.0` on the commit before the change, for anyone who needs to stay on the old scale).

3. **An agent can't write `TODO` with the CLI, even though the docs and the project instructions say to use it.** The README says `Human-Review = "TODO"` is meant for "when an agent declares its part and a person adds the human review later", and the project instructions tell Claude to use TODO until Pascal sets H. But `aidecl annotate -H TODO` and `--inline` are rejected by argparse (`choices=H0..H3`), so the only way is to edit the TOML by hand. There are two possible fixes:
   - accept `TODO` for `-H` (and `--reviewed-by TODO`) in `annotate`, skipping the completeness check for that axis;
   - or change the docs to say "edit AIDECL.toml by hand".

   Related: the lint message for every TODO says "(left by 'aidecl migrate')" (`model.py`, `validate`), which is misleading when an agent left the TODO.

4. **`pyproject.toml` still describes the old scale.** The `description` reads "AI review (A-, A0-A3)". `__init__.py` and the CLI help already say A0-A3. This is the only stale scale string I found.

5. **`AI-Review = "A-"` in a version-3 `AIDECL.toml` gives no migrate hint.** `config.py` raises `invalid AI-Review 'A-' (use A0, A1, A2, A3)`, which is exit code 2. The same value in `[policy]`, inline tags or the PR check does say "A- is now A0; run 'aidecl migrate'". Someone who bumps `version = 3` by hand without migrating gets the less helpful message. This is cosmetic.

6. **The tools don't enforce the review-file rule.** Neither the PR check nor `aidecl lint` checks that `reviews/pull#.md` or `commit#.md` exists for A2 or A3. That may be intentional, but right now the rule relies on honesty alone. Two other gaps:
   - The `commit#` naming has a chicken-and-egg problem: a review can't be committed inside the commit whose hash names it. CONTRIBUTING.md could say "the reviewed commit; commit the review in a follow-up".
   - `aidecl init` could write `exclude = ["reviews/**"]` by default.

7. **Small inconsistency:** the repo's own `AIDECL.toml` names the model as `Claude (Anthropic), claude-opus-5-5`, while the README, CONTRIBUTING.md and the project instructions use `Claude Opus 5.5 (Anthropic)`. Both are valid, but the repo doesn't follow its own example.

### Project instructions vs the repo

Mostly accurate. Four points:

- **"Last matching annotation wins; inline tags beat AIDECL.toml"** is incomplete. Inline tags win per axis: a missing axis is filled from the matching annotation. They also stop winning when the annotation sets `precedence = "override"`.
- **TODO for H:** as finding 3 says, Claude can't follow this rule with `aidecl annotate`; it has to edit `AIDECL.toml` or the header by hand. It's also worth stating what happens next. `lint` fails, and so does the PR check (`Human-Review: TODO` isn't H0-H3, and no H box is ticked), until Pascal fills it in. That is probably the intended gate.
- **The PR template also needs "I take responsibility for this change" ticked.** The PR check fails without it. The instructions should say Claude leaves that box, and the H boxes, for Pascal.
- **Clash with Claude's PR footer:** the PR check requires the declaration trailers to be the **last paragraph** of the PR body. Only `Signed-off-by:` and `Co-authored-by:` may be mixed in. Claude Code's standard footer ("🤖 Generated with Claude Code" plus a session link) normally goes at the very end, which would fail the check. The instructions should say the footer goes **above** the trailer block. Commit messages are fine: `Co-Authored-By:` is an allowed trailer.

Not mentioned in the instructions but probably worth one line: `aidecl migrate` for repos still on version 1 or 2.

### What I checked

- **aidecl:** all of `src/aidecl/*`, `tests/test_aidecl.py` (68 test functions, covering the G0/A1 rule, the policy floor and the v2 migrate cases), the README, `pyproject.toml`, `AIDECL.toml` and the 3 workflows.
- **Org `.github` repo:**
  - CONTRIBUTING.md and PULL_REQUEST_TEMPLATE.md;
  - the reusable workflows `ai-declaration.yml`, `aidecl.yml` and `ai-badge.yml`, and their workflow templates;
  - SETUP.md and `profile/README.md`.
