# Contributing

Thanks for contributing to `python-hcl2`. For any sizable change, please open an issue first so we can agree on the approach before you spend time on it.

The workflow below exists because this parser is bidirectional: almost every change has a counterpart somewhere else in the pipeline, and a change that looks correct in isolation can quietly break round-tripping. Running the checks locally and reviewing the PR before asking a human to read it catches most of that.

## The short version

1. Make your change, with tests.
1. Get the **full test suite** and **pre-commit** passing locally.
1. Open a **draft** PR.
1. Run `/review-pr <number>` against it and act on the findings.
1. Mark it ready for review.

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

## 5. Verify with `/review-pr`

```
/review-pr <number>
```

This is a [Claude Code](https://claude.com/claude-code) skill defined in `.claude/skills/review-pr/`. It runs autonomously and then reports; it does not change your branch or post anything to GitHub without asking.

What it does:

| Phase | What it checks |
|---|---|
| Issue validation | Reproduces the linked issue's exact snippet and confirms your change actually fixes it |
| CLAUDE.md compliance | The hard rules above, plus the full checklist when a language construct is added |
| Code review | Per-area review of grammar, transformer, rule classes, reconstructor, deserializer and test coverage |
| Tests | Full suite, plus edge cases derived from what the review found |

It finishes with findings graded Critical / Warning / Info, and asks how you want to proceed. Add `--skip-tests` to skip the test phase if you have just run it yourself.

Treat the output as a first reviewer, not a verdict. It is good at the mechanical checks — a missing deserializer path, a test that passes without the fix applied, an edge case the change does not cover — and those are exactly the things that otherwise get caught late. It can also be wrong, so push back where you disagree.

Fix what it finds, push, and re-run it if the changes were substantial.

## 6. Mark ready for review

Once the suite is green, pre-commit is clean and you have addressed the review findings, mark the PR ready. Note that CI does not run automatically on pull requests from forks until a maintainer approves the workflow, so your local run may be the only signal for a while — which is why step 3 matters.

## Notes on conflicts

`CHANGELOG.md` conflicts often, because every change appends to the same list. When you resolve it, keep both entries and put the one already on `main` first, so your diff stays a pure append.

For anything else, prefer merging `main` into your branch over rebasing. It avoids a force-push and keeps your commits intact.
