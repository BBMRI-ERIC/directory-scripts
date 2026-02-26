---
name: assertive-quality-gate
description: "Enforce a quality gate for this repository: assertive programming, Python API documentation quality, pytest/hypothesis test adequacy, and developer documentation updates. Use this skill before every push, when the user asks to review code, and when the user asks to test code, especially for reusable modules such as directory.py and for plugins in checks/."
---

# Assertive Quality Gate

Apply this workflow as a required gate before push, and as the default process for code review or testing requests.

## Step 1: Identify scope and risk

- Inspect changed files and classify risk.
- Prioritize reusable modules first (`directory.py`, shared helpers), then script-level changes.
- Detect whether `checks/` was changed; if yes, enable the checks-specific validation in Step 6.

## Step 2: Enforce assertive programming

- Verify that critical assumptions are defended explicitly.
- Add assertions or explicit error checks for:
  - required inputs and configuration values
  - required columns/keys in structured data
  - preconditions before destructive operations
  - impossible states in branching logic
- Prefer actionable error messages that state what is missing, where, and how to fix.
- Avoid silent fallback for ambiguous or risky behavior.

## Step 3: Enforce Python API documentation

- Ensure public classes, methods, and reusable functions have proper docstrings.
- Use one consistent Python docstring style across touched code (Google or NumPy style), and keep parameter/return/raises information complete.
- Prioritize reusable modules, especially `directory.py`, for complete and accurate doc coverage.
- Remove stale docstrings that no longer match behavior.

## Step 4: Enforce tests with pytest and hypothesis

- Add or update tests for changed logic; do not rely on manual validation only.
- Use `pytest` for unit/integration tests.
- Use `hypothesis` when data-shape variability or parser/transform robustness matters.
- Focus on:
  - happy path
  - boundary conditions
  - invalid inputs and failure paths
  - regression tests for fixed bugs
- If full test coverage is not feasible in one change, document the precise gap and risk.

## Step 5: Keep developer documentation current

- Update developer-facing docs (`README.md`, operational notes, per-script usage) when behavior, options, or workflows change.
- Keep examples executable and aligned with current CLI/API semantics.
- State non-obvious operational constraints explicitly (credentials, safety gates, side effects).

## Step 6: Additional gate for `checks/` changes

When files in `checks/` are modified, enforce all of the following:

- Use `make_check_id(...)` with identifiers that are specific, stable, and aligned with actual check purpose.
- Ensure every `DataCheckWarning(...)` message is actionable:
  - identify the offending entity
  - describe the violated rule clearly
  - include enough context to reproduce and fix
- Validate warning severity is appropriate (`ERROR`, `WARNING`, `INFO`) for the impact.
- Ensure messages avoid vague wording and hidden assumptions.

## Step 7: Execute verification commands

Run a representative verification set from repo root:

```bash
python3 -m py_compile <changed-python-files>
pytest -q
```

Run targeted checks when relevant:

```bash
pytest -q -k "<module_or_feature>"
```

If `hypothesis` tests are added or changed, run the affected subset explicitly.

If tests cannot run in the environment, report the exact blocker and provide concrete commands for local execution.

## Step 8: Report outcome in strict format

For review/test requests, report in this order:

1. Findings (highest severity first, with file references)
2. Test status (what was run, what passed/failed, what was not run)
3. Residual risks and explicit follow-ups

For pre-push gating, block push when high-severity findings or unaddressed critical test gaps remain.
