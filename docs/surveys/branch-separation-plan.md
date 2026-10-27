# Survey Branch Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Native execution is recommended for this tightly coupled Git migration.

**Goal:** Keep the default checkout simple while preserving the complete SO2/MuCP implementation and pending changes on `survey-analysis`.

**Architecture:** Preserve the current survey tree in a local recovery commit. Clean `master`, then create `survey-analysis` from that cleaned commit and restore the survey implementation plus dedicated documentation. Shared modules remain inherited from `master`; neither published history nor private artifacts are rewritten.

**Tech Stack:** Git, Python, pytest, Markdown, existing standalone survey CLIs and dependency files.

**Spec:** [Approved separation design](branch-separation-design.md).

## Global Constraints

- Same public repository; separation is not access control or history erasure.
- Preserve existing command names and root-level survey entry points on the survey branch.
- No packaging or installation of `directory.py`; no installations, cache purge, data refresh or report regeneration in this task.
- Preserve unrelated edits and all private inputs, reviewed mappings, outputs and editor artifacts. Never use blanket staging, cleanup, destructive reset or force-push.
- All detailed survey documentation and agent knowledge belongs in `docs/surveys/` on `survey-analysis`, not on `master`.
- Keep defensive private-data exclusions on both branches.
- Keep core exporters, EOSC matching, maps and shared Directory functionality on `master`.
- Do not fix unrelated baseline failures or change survey semantics during separation.
- Review and validate both resulting trees before publication; publish the survey branch first.

## Review Focus

1. Dirty working tree: every approved pending edit survives in the recovery snapshot and survey tree, with unrelated/private artifacts unchanged (Tasks 1 and 5).
2. Hidden dependencies: non-prefixed tests and dynamically imported dependencies move with their consumers; no retained core import breaks (Tasks 1, 2 and 5).
3. Documentation boundaries: shared cache/quality contracts embedded among survey paragraphs remain on `master`; extracted survey requirements remain complete (Tasks 2 and 4).
4. Future merges: a later core-only merge must not delete restored survey files or replay cleanup conflicts (Task 5).
5. Private-data-free clones: synthetic survey workflows and core tests work without ignored local overrides or real respondent data (Tasks 3 and 5).

## File Ownership

Create these documents only on the survey branch:
`docs/surveys/{README.md,so2.md,mucp.md,upsets.md,DEVELOPMENT.md,AGENTS.md,branch-separation-design.md,branch-separation-plan.md}`.
The implementation ledger is this plan's checkboxes plus concise evidence entries; temporary inventories and logs live in ignored `data-check-cache/survey-branch-separation/`.

The survey production allowlist currently consists of these 20 root files:

```text
survey-so2-directory.py
so2_descriptive_report.py
so2_descriptive_upsets.py
so2_eusurvey.py
so2_readiness_scores.py
so2_response_merging.py
so2_response_profiles.py
survey_combined.py
survey_combined_cohort.py
survey_combined_intersections.py
survey_combined_quantity_views.py
survey_combined_report.py
survey_combined_tables.py
survey_descriptive.py
survey_evidence.py
survey_identity.py
survey_mucp.py
survey_mucp_aggregation.py
survey_mucp_quantities.py
survey_mucp_reviewed.py
```

Other survey-owned files: all currently tracked `survey-mappings/` files; tracked `tests/test_so2_*.py`, `tests/test_survey_*.py`, `tests/test_mucp_*.py`; `tests/test_quantity_reporting_audit.py`; tracked `tests/fixtures/so2_mucp/`; and `docs/so2-descriptive-upsets.md` (relocated to `docs/surveys/upsets.md`). Resolve these selectors to explicit paths in the inventory before removing anything. Inspect import consumers to find additions, rather than treating the selectors as an exhaustive proof.

Shared files to edit narrowly: `.gitignore`, `README.md`, `AGENTS.md`, `DEVELOPMENT.md`, `docs/auxiliary-tools.md`, `requirements.txt`. New shared test: `tests/test_distribution_boundary.py`. Survey-only additions: `requirements-surveys.txt`, `tests/test_survey_branch_boundary.py` and dedicated docs above.

## Task 1: Freeze And Preserve The Starting State

**Files:** Existing ten pending tracked files listed below; approved design and this plan; ignored inventory/log directory.

**Interfaces:** Produces `BASE` (verified starting master SHA), `SNAPSHOT` (recovery commit SHA), explicit ownership manifest and protected-local-artifact inventory. Record these exact values in the ledger; later tasks consume them rather than guessed branch tips.

- [x] Fetch remote refs and inspect `git status --short`, `git branch -vv`, `git log -5 --oneline` and `git diff --stat`. Reconcile any remote advance without losing local edits. Planning baseline was `69ff5ada73904ef06f59ebc044a77db416a66a6b`; do not assume it is still current.
- [x] Confirm the pending tracked allowlist is `.gitignore`, `DEVELOPMENT.md`, `docs/auxiliary-tools.md`, `so2_readiness_scores.py`, `survey-mappings/mucp_answer_states_v1.json`, `survey_combined.py`, `survey_mucp.py`, and their three tests: `tests/test_so2_readiness_scores.py`, `tests/test_survey_combined.py`, `tests/test_survey_mucp.py`. Inventory any additional edits separately; do not silently include them.
- [x] Create an ignored, explicit ownership manifest with tracked path, role (`shared` or `survey`), Git blob/hash and intended destination. Scan Python imports plus textual/dynamic references. Include `tests/test_quantity_reporting_audit.py` and `importlib.import_module("javaobj.v2")` in the audit.
- [x] Inventory private/ignored survey artifacts and unrelated untracked files with paths, sizes and content hashes for protected regular files. Exclude active runtime caches/logs from strict byte equality, recording that exclusion. Keep this inventory local; do not place filenames or respondent content into published docs.
- [x] Record baseline pytest collection IDs and run `pytest -q`, saving a local log. Record actual failures/skips and environment. The earlier baseline was 1253 passed, 39 skipped and 8 failures; it is context, not permission to ignore a new failure.
- [x] Create a local `survey-preservation-20261027` branch from `BASE` while preserving working edits. If the name exists, use an unused numeric suffix and record it; never reset an existing reference.
- [x] Review the pending delta and run `pytest -q tests/test_so2_readiness_scores.py tests/test_survey_combined.py tests/test_survey_mucp.py`. Resolve in-scope regressions; do not merely archive failing new functionality.
- [x] Stage only the ten reviewed files, approved design and this plan. Inspect `git diff --cached --stat` and the complete staged diff for private material. Commit the recovery snapshot and record `SNAPSHOT`.
- [x] Save a read-only checkpoint copy of design, plan and inventory in the ignored local directory before switching back to `master`, where newly tracked survey docs will disappear. Verify the snapshot contains all pending source changes. Leave unrelated artifacts untouched.

**Checkpoint:** Recovery commit exists locally, tests recorded, no published refs changed. Do not push the recovery branch as a third maintained branch.

## Task 2: Produce A Clean Core Master

**Files:** Shared files identified above; create `tests/test_distribution_boundary.py`; remove only manifest-listed survey files.

**Interfaces:** Consumes `BASE`, `SNAPSHOT` and manifest. Produces cleaned core commit `CORE`. The common boundary test supports both distributions by tracked file presence, not current branch name, so detached checkouts remain valid.

- [x] Add documented tests `test_distribution_inventory_contract` and `test_distribution_contract_accepts_both_supported_layouts`. Read tracked paths using `git ls-files`; detect survey distribution by tracked `docs/surveys/README.md`. Assert core Directory/check/exporter/EOSC/map entry points remain in both layouts. In core layout assert the manifest's survey modules, mappings, fixtures and survey-specific tests are absent. In survey layout require survey CLI, mappings, docs and extra requirements.
- [x] Test both inventory modes using invented path sets, including rejection of a core layout with a residual non-prefixed survey consumer. Run `pytest -q tests/test_distribution_boundary.py`: the actual pre-cleanup checkout must fail the core inventory assertion. This is the red gate, not an unexplained test error.
- [x] Remove only audited tracked survey paths via an explicit allowlist. Do not remove `R-maps/` strategic-objective examples or shared helpers. Do not delete ignored files from `survey-mappings/`.
- [x] Extract survey material from shared docs using the snapshot as the authoritative source. Retain shared QC workflow, confidence/selection rules, withdrawal, EOSC and fact-sheet specifications. In particular retain the `directory.py` cache-first/fallback and quality-table/ontology-cache paragraphs currently embedded under SO2, relocating them into an appropriate shared Directory section.
- [x] Replace the README survey listing/paragraph with one short link to `https://github.com/BBMRI-ERIC/directory-scripts/tree/survey-analysis/docs/surveys`. Remove detailed survey guidance elsewhere on core; retain all non-survey auxiliary tool instructions. Use fence-aware headings when extracting shell examples.
- [x] Recheck dependency consumers. Remove `javaobj-py3==0.6.1`, `defusedxml~=0.7.1` and `jsonschema>=4.17.3,<5` from core requirements only if no retained consumer needs them. Carry the pending private-input ignore additions from `SNAPSHOT` onto core, without restoring other survey changes.
- [x] Run the boundary test green, `git diff --check`, retained-module import/reference checks and local Markdown link checks. Check retained Python test collection against baseline minus the explicit survey-owned tests, so cleanup cannot accidentally hide core tests.
- [x] Review the complete `BASE..working-tree` core delta, stage exact paths and commit `CORE` on local `master`. Do not publish yet.

**Checkpoint:** Core checkout contains normal tools without survey dependencies or broken survey imports. Recovery snapshot still contains all removed content.

## Task 3: Restore A Maintained Survey Distribution

**Files:** Survey allowlist from snapshot; create `requirements-surveys.txt`, `tests/test_survey_branch_boundary.py`, `docs/surveys/README.md`.

**Interfaces:** Consumes `CORE`, `SNAPSHOT`, manifest and common boundary test. Produces `survey-analysis` descended from `CORE`, with original survey implementation and independent dependency entry point.

- [x] Create `survey-analysis` from `CORE`. If a branch with that name already exists, inspect it and reconcile explicitly; never overwrite it. Restore only survey-owned tracked files from `SNAPSHOT`, not old common Markdown or whole shared requirements.
- [x] Add documented tests `test_all_survey_cli_commands_are_retained`, `test_survey_reference_defaults_exist`, and `test_survey_dependencies_include_core_requirements`. Require all eight existing peer commands: `analyze`, `describe`, `render-report`, `render-descriptive-report`, `export-update-plan`, `export-eus-form-json`, `export-descriptive-upset-r`, `merge-mucp`. Confirm the precise UpSet command spelling from the parser before freezing the test.
- [x] Run the new tests red against the incomplete restored tree; failure must identify missing survey packaging/docs/defaults, not require real respondent inputs.
- [x] Create the survey docs index marker and `requirements-surveys.txt` with `-r requirements.txt` and only the survey dependencies removed in Task 2, retaining their versions. Document optional external R/TeX/Java requirements rather than installing anything.
- [x] Run `python3 survey-so2-directory.py --help` and help for all eight commands; run `pytest -q tests/test_distribution_boundary.py tests/test_survey_branch_boundary.py tests/test_survey_merge_mucp_cli.py tests/test_survey_merge_mucp_integration.py`. Synthetic CLI publication and validation paths must work without private review files.
- [x] Compare every restored source/mapping/test blob with `SNAPSHOT`; allow only explicitly documented distribution-test or documentation changes. Commit the restored survey distribution after these checks pass.

**Checkpoint:** Pending readiness, MuCP metadata and ambiguous-answer-state changes survive exactly; no statistical/reporting behavior is redesigned.

## Task 4: Consolidate Survey Knowledge Without Shared-Doc Drift

**Files:** All eight dedicated survey documents; shared README, AGENTS, DEVELOPMENT and auxiliary guide; remove old standalone UpSet guide after relocation.

**Interfaces:** Consumes the complete pre-cleanup Markdown from `SNAPSHOT`. Produces a paragraph/requirement coverage ledger mapping original heading or rule to its canonical new location or retained shared contract.

- [x] Build a source-to-destination checklist: initial SO2 analysis and descriptive workflows -> `so2.md`; combined analysis/identity/quantity workflows -> `mucp.md`; native/proot R and embedding -> `upsets.md`; all normative survey invariants -> dedicated `DEVELOPMENT.md`; survey guardrails -> dedicated `AGENTS.md`.
- [x] Move full substantive content, including the pending documentation changes, not just summaries. Preserve form validation, provenance, joins, collection scopes, aggregation caveats, atomic publication, chart behavior, readiness scoring and duplicate-response rules. Record any pre-existing contradictory instructions instead of silently changing functionality to reconcile them.
- [x] Update relative links from `docs/surveys/` to root code/mappings using `../../...`. Keep one canonical R workflow and link to it from SO2/MuCP guides. Retain public acknowledgements and remove no legitimate attribution under the guise of note sanitation.
- [x] Restore the approved design and this plan under `docs/surveys/`; maintain execution evidence here. Add a minimal root AGENTS pointer on the survey branch requiring maintainers working on survey files to read `docs/surveys/AGENTS.md`, because directory-scoped agent files do not automatically govern root Python files.
- [x] Keep root README identical to cleaned core where practical and root DEVELOPMENT/auxiliary guide identical to `CORE`. No detailed survey instructions are reintroduced into common docs. Explain installation via `requirements-surveys.txt` and the maintenance direction `master -> survey-analysis` in the dedicated index.
- [x] Validate all moved local links and fence-aware headings, compare the requirement checklist with snapshot content, and run existing Markdown sanitation/documentation checks identified by `git ls-files tests`. Verify both core cache/quality paragraphs survive in core and every survey requirement has a destination.
- [x] Run `git diff --check`, inspect staged documentation for private/person-specific notes and commit the documentation consolidation on `survey-analysis` only.

**Checkpoint:** No knowledge is stranded in common documents or local-only notes; no private data is added to Git.

## Task 5: Validate Isolated Trees And Future Merge Safety

**Files:** Ignored verification worktrees/logs; test changes only for actual migration defects; evidence ledger.

**Interfaces:** Consumes final `CORE` and survey tip `SURVEY`. Produces clean-clone verification evidence, trial-merge proof and one independent completion audit.

- [x] Use the worktree skill to create detached Git verification worktrees under the ignored checkpoint directory for both tips. Unlike a plain archive, these support repository tests using `git ls-files`. Do not copy private survey inputs, `.env`, caches or reviewed local mappings into them.
- [x] In core, run `pytest -q tests/test_distribution_boundary.py tests/test_cli_help.py tests/test_python_docstring_contract.py`, then `pytest -q`, with logs. Compile changed Python tests. Compare failures and collected retained tests with Task 1, not just total counts.
- [x] In survey, run `pytest -q tests/test_distribution_boundary.py tests/test_survey_branch_boundary.py tests/test_survey_so2_directory.py tests/test_so2_readiness_scores.py tests/test_quantity_reporting_audit.py tests/test_survey_merge_mucp_cli.py tests/test_survey_merge_mucp_integration.py`, then `pytest -q`. Run all peer-command help and required code/doc contract checks. Record optional local replay skips explicitly; synthetic acceptance cases cannot be skipped as a substitute.
- [x] Verify manifest source hashes against `SNAPSHOT`, exact pending-change preservation, shared-core source equality between tips, and documentation extraction coverage. Recheck protected private files against Task 1 hashes without publishing their inventory.
- [x] Create a harmless README-comment probe commit parented at `CORE` in a disposable detached checkout. Merge that probe into a disposable checkout at `SURVEY`; require no cleanup-related conflict, identical survey code/docs hashes and passing boundary/CLI checks. Never publish the probe commit or merge.
- [x] Obtain one independent read-only Sol 6.1 medium audit of the whole two-tree delta against the original requirements/design, inventory and evidence. Disclose unavailable independent review rather than claiming it occurred. Fix in-scope findings, rerun invalidated checks and re-review affected areas.
- [x] Record exact final tips and baseline failures. Earlier eight failures involved CLI/Yapsy, exporter documentation format and R-map test environment; each still needs classification from current evidence. No new unexplained failure is acceptable, and no core test may be deleted to make the migration green.

**Checkpoint:** Both distributions verified without private data, future merge tested, implementation audit resolved. No remote changes yet.

## Task 6: Publish Safely And Hand Over

**Files:** Final ledger only; Git refs/publication state.

**Interfaces:** Consumes audited `CORE`, `SURVEY`, expected remote baseline and local recovery reference. Produces verified remote tips and practical branch instructions.

- [ ] Apply the repository review-and-commit/quality-gate requirements to the complete task delta, reusing valid Task 5 evidence. Verify `git diff --check`, precise staging, no unrelated tracked modifications and no private artifacts in either publication delta.
- [ ] Fetch again and compare remote master with the expected baseline. If it advanced, preserve both local tips and integrate its actual changes safely, then rerun affected checks; do not force-push. Check for an existing remote survey branch before publication.
- [ ] Push `survey-analysis` first and verify its remote SHA. Only then push cleaned `master` and verify its remote SHA. If the second push fails, retain the published survey recovery route and report the exact state; do not undo either branch destructively.
- [ ] Return the main workspace to `master`, confirm no task-owned tracked edits remain, and recheck protected artifacts. Keep the local recovery reference until successful publication is confirmed. Remove only disposable worktrees created by this task once their logs/evidence are retained; never run general workspace cleanup.
- [ ] Report both commit IDs, verification/baseline limitations and that private artifacts were untouched. Provide `git switch survey-analysis` and `git switch master`, plus the optional operator installation command `python3 -m pip install -r requirements-surveys.txt`. Warn against wholesale merging the survey branch back to master.

## Recovery And Outstanding Decisions

Before publication, `SNAPSHOT` is the complete surveyed-code recovery source; reconstruct with reviewed allowlisted restores/new commits, not a destructive reset of the user's checkout. After publication, repair with reviewed forward commits or explicitly approved reversions, never rewritten history. A failed publication must leave both exact local tips and the recovery reference recorded.

There are no outstanding product-design decisions. Execution must still detect branch-name collisions, remote advancement, unexpected unrelated edits and any dependency consumer missed by this inventory; these are safety checks, not authorization to discard or overwrite them.

## Execution Evidence

- Planning only: design approved; current ten pending tracked changes and untracked/private artifacts left untouched. No branches created, source files removed, commits made or refs pushed during plan preparation.
- Task 1: `BASE=69ff5ada73904ef06f59ebc044a77db416a66a6b`, matching fetched origin/master. Local recovery branch: `survey-preservation-20261027`. Inventory: 313 tracked paths, 73 survey-owned paths, zero retained core import consumers, 1128 protected local files. Full baseline: 1253 passed, 39 skipped, eight existing failures in 175.61 seconds. Pending-feature targeted suite: 96 passed; changed Python compile checks passed. Exact logs and private inventory remain ignored locally.
- Task 2 red gate: common distribution contract added before cleanup; the real checkout fails because tracked survey files are still present without the survey-distribution marker. Invented-layout checks exercise both supported distributions and incomplete restoration.
- Task 1 complete: recovery `SNAPSHOT=bf084c22c40bffc1b0b1ca478e7ef97f0be48e17` retains all ten pending edits and approved planning documents. Private files were not staged.
- Task 2 complete: `CORE=e0d7c324414a22de3ffb53590908fd725839cd4c`; boundary/doc-contract/Markdown checks: 22 passed. Shared cache and quality rules retained; survey-only dependencies removed after consumer audit. No core production Python changed.
- Task 3 complete: survey branch created from CORE, all original source/mapping/test blobs restored exactly from SNAPSHOT. Boundary red gate: two expected failures for absent index/extras, eight command-help passes. Green restoration/CLI/synthetic integration suite: 29 passed. Dedicated docs and dependency files added; full documentation extraction follows.
- Task 4: survey restoration commit `a80af66`; complete operator/specification/guardrail extraction under dedicated docs. Shared root README, DEVELOPMENT, auxiliary guide, requirements and ignores match CORE exactly; root AGENTS differs only by its survey-instructions pointer. Source preservation and all relocated Markdown file/anchor checks passed. Historical compiler/deviation documentation discrepancies are explicitly recorded without changing behavior.
- Task 4 complete: documentation commit `031eb14`; boundary/help/doc-contract/Markdown suite: 32 passed. The independent read-only Sol 6.1 medium audit found no substantive migration findings and confirmed all 72 restored artifacts match SNAPSHOT (the 73rd artifact is the relocated guide).
- Task 5 merge evidence: disposable later core-only README commit merged cleanly into the survey tree; only the probe README changed, survey source/docs hashes survived, and 12 boundary/help tests passed. The probe remains unpublished.
- Task 5 isolated evidence before the final test-safety correction: core full suite 582 passed, 40 skipped, eight baseline failures; survey full suite 1263 passed, 41 skipped, the same eight baseline failures. Targeted survey suite 130 passed, one private replay skipped. Collection comparison: zero unexpectedly lost core tests and zero lost survey tests; new boundary cases account for added tests. Git ownership required command-scoped safe.directory environment settings for Android shared-storage worktrees, without global config changes.
- Ruling: extend scope only to isolate the pre-existing cMDR smoke test's output, because baseline verification exposed it overwriting an existing local synthetic workbook. A temporary canary reproduced the defect; explicit temporary output plus an isolated working directory fixes it. Core commit `ea44a2b` adds the regression and shared test-safety guidance; merged into survey as `9ebaae7` without conflict. No core production logic changed. Cost if wrong: missed test side effects could still affect a developer checkout; isolated final suites and sentinel assertions guard this path.
- Preservation exception: the initial baseline run rewrote local `cMDR.xlsx`; its earlier exact ZIP bytes are not recoverable from the hash-only inventory. This is not claimed as preserved. The other detected change was Hypothesis runtime Unicode cache data, not a survey source. All other 1126 inventoried protected files, including private survey inputs, reviewed decisions and survey reports, matched their recorded hashes. Future verification runs use isolated checkouts; do not rerun the unsafe old baseline in the main checkout.
- Accounting: one independent completion reviewer used verified runtime model `gpt-6.1-sol`, effort `medium`; no implementation children. Weekly allowance telemetry unavailable. Existing baseline failures remain explicit rather than weakened or repaired outside scope. Final isolated suites are being rerun after the test-only safety correction.
- Task 5 complete: final isolated CORE `ea44a2b` full suite: 582 passed, 40 skipped, eight baseline failures (70.12 seconds); final survey `9ebaae7`: 1263 passed, 41 skipped, the identical eight baseline failures (194.89 seconds). No new failed test IDs. Skips include unavailable R/live dependencies and private source-bound replay, not omitted synthetic acceptance tests. Final source/link checks passed. All substantive extracted operator/specification/agent/UpSet lines survived; one moved heading was renamed. Incremental independent audit of `ea44a2b` found no substantive issues.
- Ruling: retain the eight demonstrated pre-existing failures rather than fixing unrelated CLI/Yapsy, exporter-format and R-map environment issues. The approved separation design explicitly requires baseline comparison and prohibits unrelated repairs. Cost if wrong: those existing tools/tests remain affected in this environment; the migration does not claim a fully green suite.
- Update this section at task boundaries with SHA values, tests, failures, audit findings and next action. Do not include private inventories or respondent details.
