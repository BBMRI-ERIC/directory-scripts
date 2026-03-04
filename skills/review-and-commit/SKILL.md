---
name: review-and-commit
description: Review current repository changes, run the required quality checks and targeted tests, update repository and manual documentation, refresh AGENTS/skills guidance, and create a safe commit with a comprehensive message body. Use when the user asks to review work before commit, to commit current changes, or to perform the final pre-commit quality pass in this repository.
---

# Review And Commit

Run this workflow before creating a commit in this repository.

## Workflow

1. Inspect the scope.
- Run `git status --short`.
- Separate tracked source changes from local artifacts.
- If multiple repositories are involved (for example `directory-scripts` and `../BBMRI-ERIC-Directory-Data-Manager-Manual`), treat them as separate commits unless the user explicitly wants otherwise.

2. Review correctness, safety, and error handling.
- Check that changed code has adequate runtime validation and user-facing error handling.
- Verify expected exceptions are handled where the tool should continue gracefully.
- Verify uncommon exceptions are either intentionally allowed to fail fast or are converted into clear user-facing errors when the tool cannot proceed safely.
- For write paths and destructive operations, verify confirmation, dry-run, and force semantics remain coherent.

3. Apply repository quality gates.
- Use `assertive-quality-gate` for changed code.
- Use `review-check-redundancy` before committing changes in `checks/`, `text_consistency.py`, `checks/AIFindings.py`, `ai_cache.py`, or `ai-check-cache/`.
- If a change affects updater workflows, verify the user-facing review/apply behavior, not only the internal logic.

4. Validate code documentation and tests.
- Check/update docstrings for changed reusable modules, public functions, and classes.
- Check unit-test coverage for the changed behavior.
- Add regression tests for fixed bugs and changed workflows.
- Run `python3 -m py_compile` on touched Python files.
- Run targeted `pytest -q` subsets first.
- Run broader tests when the risk justifies it.
- Do not commit until the relevant unit tests pass.

5. Check documentation consistency.
- Update `README.md` for user-facing behavior changes.
- Update `DEVELOPMENT.md` for developer-facing architecture/workflow changes.
- Update `AGENTS.md` with new guardrails learned from bugs, reviews, or merged PRs, and keep older guidance intact unless it is truly obsolete.
- If a skill workflow changed, update the corresponding skill and validate it with `quick_validate.py`.
- Check consistency between code, `README.md`, `DEVELOPMENT.md`, `AGENTS.md`, and the relevant skills.

6. Check manual consistency when relevant.
- If the change affects QC tooling, QC helper workflows, check documentation, or other user-facing validation/update workflows, inspect `../BBMRI-ERIC-Directory-Data-Manager-Manual/BBMRI-ERIC-Directory-Data-Manager-Manual.tex`.
- Update the manual when the QC tooling or its helper workflows changed.
- This manual-sync requirement applies to QC tooling and QC-related helper tools, not to unrelated auxiliary scripts such as exporters unless the user asked for it.
- If check documentation extraction changed, also validate `../BBMRI-ERIC-Directory-Data-Manager-Manual/scripts/generate_checks_docs.py` when relevant.

7. Stage only the necessary files.
- Include source, tests, docs, AGENTS, skill files, and manual files needed for the new behavior.
- Exclude local artifacts such as XLSX outputs, caches, generated temporary files, editor backups, and ad hoc review outputs unless the user explicitly wants them committed.
- Be careful with renames so required runtime files are not accidentally left untracked.
- Verify that all files required for correct runtime operation of the updated tooling are tracked and staged as needed; do not leave newly introduced runtime/source files untracked just because the current diff happens to exercise them locally.

8. Commit after validations pass.
- Once the required validations succeed, create the commit at the end of the workflow.
- Use a short present-tense subject.
- Add a comprehensive body that covers:
  - the main behavior changes
  - important safety or workflow implications
  - tests/validation run
  - any intentionally deferred limitations

## Required checks for common change types

- `checks/` changed:
  - validate check IDs/messages
  - run targeted plugin tests
  - run redundancy review
  - check CHECK_DOCS/manual consistency when relevant
- updater or fixer workflow changed:
  - check that any newly introduced helper/runtime files are actually present in the repository and not only in the local worktree
  - test dry-run, interactive, and force semantics as relevant
  - test mismatch handling, append/replacement presentation, and no-op handling
  - update README, DEVELOPMENT, AGENTS, and the manual when QC helper behavior changed
- `directory.py` or auth/schema logic changed:
  - test both default `ERIC` behavior and non-`ERIC` authenticated behavior
  - verify user-facing errors for missing credentials/configuration
- skills changed:
  - sync any installed local copy if the workflow depends on it
  - run `python3 /data/data/com.termux/files/home/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-path>`

## Output expectation

Report briefly:
- what was validated
- what was staged
- commit hash and subject
- any remaining untracked artifacts or follow-up risks
