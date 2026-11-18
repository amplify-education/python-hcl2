# Contributing

Thanks for contributing to `python-hcl2`. For any sizable change, please open an issue first so we can agree on the approach before you spend time on it.

The workflow below exists because this parser is bidirectional: almost every change has a counterpart somewhere else in the pipeline, and a change that looks correct in isolation can quietly break round-tripping. Running the checks locally and reviewing the PR before asking a human to read it catches most of that.

## The short version

1. Make your change, with tests.
1. Get the **full test suite** and **pre-commit** passing locally.
1. Open a **draft** PR.
1. Self-review it against [the checklist](#5-self-review-before-asking-for-review) — by hand, or automatically if you use Claude Code.
1. Mark it ready for review.

No particular tooling is required. Step 4 has an automated shortcut for Claude Code users, but the checklist is the actual requirement and doing it by hand is perfectly fine.

## 1. Set up

```bash
python -m pip install --upgrade -r test-requirements.txt -e .
pre-commit install
```

## 2. Make the change

Read [`CLAUDE.md`](CLAUDE.md) first. It documents the pipeline, the module map, and a set of hard rules that reviewers will check against — most importantly:

- Always go through the LarkElement IR; never convert a Lark tree straight to a dict or back.
- Every serialization path needs a matching deserialization path. Parse → serialize → deserialize → serialize must produce identical output.
- One grammar rule maps to exactly one `LarkRule` class.
- Adding a language construct means touching `transformer.py`, `deserializer.py`, `formatter.py` **and** `reconstructor.py`, not just the grammar.

Tests use `unittest.TestCase` — not pytest. Unit tests live in `test/unit/`, full-pipeline tests with golden files in `test/integration/`.

## 3. Get it green locally

Both of these must pass before you open a PR.

**Tests:**

```bash
python -m unittest discover -s test -p "test_*.py" -v
```

Run the whole suite, not just the tests you added. The integration suites (`test_round_trip.py`, `test_specialized.py`) are where round-trip regressions surface, and they are easy to break from a change that looks local.

**Pre-commit:**

```bash
git add -A
pre-commit run
```

With no arguments `pre-commit run` checks the staged files, which is what the commit hook will check. Stage first — a command like `--files $(git diff --name-only origin/main)` silently skips files you have added but not staged, so a brand-new module goes unchecked.

Prefer that over `--all-files`. Two things to know about `--all-files`:

- `no-commit-to-branch` fails whenever you run it while `main` is checked out. That hook exists to stop commits to `main`, so failing there is intended and not something to fix.
- It may surface pre-existing problems in files you never touched, which makes it hard to see whether *your* change is clean.

If a hook fails and the fix isn't obvious, `/fix-precommit` will diagnose and fix it.

To reproduce CI exactly — it runs the suite across Python 3.8 through 3.13 — use `tox`.

## 4. Open a draft PR

Open it as a **draft**. Two reasons: it signals you are not asking for human attention yet, and it gives `/review-pr` something to review, since the skill works from a PR number rather than a working tree.

```bash
gh pr create --draft --fill
```

In the description, explain **why** the change is needed, not just what it does — the diff already shows the what. Link the issue it fixes (`Fixes #123`) and include a short test plan.

## 5. Self-review before asking for review

Go through this before marking the PR ready. Every item is something that has actually slipped through on this repo.

- **Does the linked issue's exact snippet now behave correctly?** Not a paraphrase of it — copy the code block from the issue and run it.
- **Does your test fail without your source change?** Stash or revert just the source edit, run the new test, confirm it fails, restore. A test that passes either way is not testing your fix. This is the highest-value check on the list.
- **Round-trip holds?** Parse → serialize → deserialize → serialize must produce identical output. If you added golden files, `json_serialized/` and `json_reserialized/` should be byte-identical for your suite.
- **Both directions updated?** A new serialization path needs its deserialization counterpart. A language construct needs `transformer.py`, `deserializer.py`, `formatter.py` and `reconstructor.py`.
- **Full suite green**, not just the tests you touched.
- **Edge cases**: empty bodies, nested constructs of the same type, interaction with interpolation, and the construct in a container (tuple element, object value, function argument).

If the change touches the grammar, also check that no existing terminal can now match in a context it previously could not.

### If you use Claude Code

The [`/review-pr`](https://claude.com/claude-code) skill in `.claude/skills/review-pr/` automates the checklist:

```
/review-pr <number>
```

It fetches the PR and its linked issue, reproduces the issue, checks the `CLAUDE.md` rules, reviews each changed area, runs the suite plus edge cases it derives from what it finds, and reports findings graded Critical / Warning / Info. It asks before changing anything or posting to GitHub. `--skip-tests` skips the test phase if you have just run it.

Treat it as a first reviewer, not a verdict — it is good at the mechanical checks and it can also be wrong, so push back where you disagree.

### If you don't

Work the checklist by hand; that is the whole requirement. Nothing in this project needs Claude Code, and a PR is never held up for lacking it.

For reference, maintainers may run `/review-pr` on your PR during review. The checklist above is what it looks for, so working through it yourself means fewer round trips either way.

## 6. Mark ready for review

Once the suite is green, pre-commit is clean and you have worked the checklist, mark the PR ready. Note that CI does not run automatically on pull requests from forks until a maintainer approves the workflow, so your local run may be the only signal for a while — which is why step 3 matters.

## Notes on conflicts

`CHANGELOG.md` conflicts often, because every change appends to the same list. When you resolve it, keep both entries and put the one already on `main` first, so your diff stays a pure append.

For anything else, prefer merging `main` into your branch over rebasing. It avoids a force-push and keeps your commits intact.
