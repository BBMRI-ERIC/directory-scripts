# Survey Analysis Branch Separation

Status: Approved design; implementation awaits plan review and execution selection.

## Purpose And Decisions

Keep the default `master` checkout focused on Directory quality checks,
exporters, maintenance, maps and shared libraries for BBMRI Nodes. Maintain the
complete SO2 and MuCP survey analysis on a long-lived branch in the same public
repository. This is checkout and maintenance separation, not access control or
Git-history erasure.

The agreed documentation home is `docs/surveys/` on the survey branch. No detailed
survey specifications, workflows or agent knowledge should remain in common
Markdown files on `master`. A short landing-page pointer is sufficient there.

Proposed branch name: `survey-analysis`.

## Approaches

- Long-lived branch in this repository: selected direction. Preserves the
  existing standalone CLI and direct imports of shared Directory modules,
  without packaging, installations or an additional repository.
- Separate survey repository: not selected. Stronger separation, but adds
  shared-library distribution and versioning work that is unnecessary for the
  stated goal of a simpler default checkout.
- A survey folder on `master`: not selected. Reduces root-level clutter but
  leaves survey-specific documentation, tests and dependencies in the normal
  Node checkout.

## Branch Topology And Preservation

Do not revert the historical survey commits wholesale: those commits include
unrelated Directory improvements that must remain available.

Before cleanup, preserve the current public survey implementation and all pending
survey source, test, mapping and documentation changes in an explicit reviewed
Git snapshot. Stage only an audited allowlist; never include private inputs,
runtime review decisions, source-bound reference data or generated artifacts.
Verify the snapshot and retain its recovery reference until both branches pass
their acceptance checks.

Create the maintained survey branch from the cleaned `master` baseline, then
reintroduce its survey-specific implementation and dedicated documentation from
the preservation snapshot. Do not merely fork before cleanup and repeatedly
merge the removal commit into the survey branch: that can propagate deletions
and introduce avoidable modify/delete conflicts.

Publish only after both resulting trees have been checked. Creating a local
preservation reference is a recovery measure, not a request to publish a third
maintained branch. Do not force-push or rewrite published history.

After separation, merge `master` updates into `survey-analysis` as needed and
run both core and survey tests there. Do not merge the entire survey branch
back into `master`. Genuine shared-core fixes originate on `master` where
practical, or are transferred as individually reviewed changes.

This arrangement reduces common-document overlap. It cannot guarantee that
changes to shared libraries or their interfaces will never require reconciliation.

## Ownership Of Files And Dependencies

Survey-only material belongs on `survey-analysis`:

- `survey-so2-directory.py`, its `so2_*.py` helpers, and the SO2/MuCP evidence,
  identity, statistics, quantity and reporting modules currently named
  `survey_*.py`.
- Survey-specific mappings and schemas under `survey-mappings/`, synthetic
  fixtures under `tests/fixtures/so2_mucp/`, and all analysis-specific tests.
- Associated documentation and survey-specific dependency declarations.

Removal is based on an audited dependency inventory, not filenames alone.
For example, `tests/test_quantity_reporting_audit.py` imports survey report
modules despite not having a survey-prefixed filename. Embedded form-decoding
helpers and any other non-prefixed assets must be included when applicable.

Keep shared modules on both branches through normal branch ancestry, including
`directory.py`, `cli_common.py`, `fix_proposals.py`, `duo_terms.py` and
`oomutils.py`. Do not duplicate these modules inside a survey subtree. Core
exporters, EOSC organisation matching and map-generation tools remain on `master`.
Strategic-objective map examples are not survey analysis merely because their
names include SO2; retain them unless an actual survey-code dependency is found.

Audit `requirements.txt` by consumer. Candidates such as `javaobj-py3`,
`defusedxml` and `jsonschema` may leave the core installation only if no remaining
core tool uses them. On the survey branch, declare survey-only dependencies in
`requirements-surveys.txt`, including the common requirements rather than
maintaining a second divergent copy. R, TeX and optional form-decoding runtime
instructions belong in the survey documentation; no installations are part of
this repository separation.

Preserve existing command names and root-level survey entry points on the survey
branch so direct execution from the clone still works without installing
`directory.py`. The shared Directory API and cache conventions remain unchanged.
No cache purge, live data refresh or report regeneration is needed for separation.

## Dedicated Documentation

On `survey-analysis`, consolidate substantive current knowledge into:

- `docs/surveys/README.md`: survey-tool overview and documentation index.
- `docs/surveys/so2.md`: SO2 analysis, form manifests, descriptive reports,
  scoring, response merging and update-plan workflows.
- `docs/surveys/mucp.md`: combined analysis, identity resolution, cohort joins,
  provenance, collection scopes, quantities and report interpretation.
- `docs/surveys/upsets.md`: external R generation, native/proot execution,
  asset validation and embedding; move the current UpSet guide here.
- `docs/surveys/DEVELOPMENT.md`: normative survey functionality specifications,
  invariants, shared-module interfaces and verification requirements.
- `docs/surveys/AGENTS.md`: enforceable survey-specific agent instructions and
  links to the detailed specifications.
- `docs/surveys/branch-separation-design.md`: this approved separation design.

Move survey sections out of `docs/auxiliary-tools.md`, `DEVELOPMENT.md` and root
`AGENTS.md`; preserve their substantive requirements rather than shortening them
into incomplete summaries. Normalise duplicate statements without weakening
contracts. Update every affected link. Do not reintroduce personal notes,
person-specific reference labels or local account paths.

Keep common Markdown as similar as possible on both branches. `master` has one
short README pointer to the survey branch, not a set of broken links to removed
files. A minimal root agent pointer on the survey branch may direct maintainers
to the dedicated survey instructions; it contains no detailed survey rules.
Generic core ownership and documentation/privacy rules stay in common guidance.

## Private Data And Local State

Keep ignored survey input, output and review-data exclusions effective on both
branches. Switching a branch does not remove ignored local files or make those
files public. Do not delete, relocate, rewrite or commit existing local inputs,
generated PDFs, R bundles, reviewed identity decisions or quantity corrections.

Preserve pending source changes in the survey snapshot before cleaning `master`.
Any unrelated tracked edits or untracked artifacts must remain untouched. Use
explicit file inventories and recovery checkpoints rather than a blanket add,
destructive reset or cleanup of untracked files.

## Validation And Completion

- Record a before/after ownership manifest covering code, mappings, tests,
  fixtures, dependencies and extracted documentation requirements.
- Validate the preservation snapshot against pending source changes and verify
  that every survey requirement and artifact expected in Git survives on the
  maintained survey branch. Private artifacts must remain local and unchanged.
- On cleaned `master`, verify that tracked core modules and tests have no imports
  of removed analysis modules, documentation links resolve, common instructions
  contain no detailed survey knowledge, and survey-only dependencies are absent
  where the consumer audit permits removal. Retain only the intended README
  pointer and defensive private-data exclusions.
- On `survey-analysis`, verify CLI help and synthetic smoke workflows for SO2
  and MuCP, default reference/config resolution, complete documentation links
  and operation without any private fixtures or local review files.
- Run relevant and full test suites on both resulting trees. Record existing
  environment/baseline failures separately; do not hide new failures by deleting
  retained core tests or weakening survey tests.
- Perform a trial merge of a harmless later core-only change into a disposable
  survey checkout, demonstrating that it preserves survey files and dedicated
  docs without replaying the cleanup deletion. Do not publish the trial change.
- Review both publication deltas for private material and unintended shared-core
  changes. Publish the survey branch before the cleaned default branch, verify
  remote branch tips, and keep the recovery snapshot until publication succeeds.

## Non-Goals And Builder Discretion

Do not redesign survey statistics, change source semantics, fix unrelated map
tests, restructure core tools, introduce a package-install requirement, create
a separate repository, restrict access or erase Git history.

The implementation plan must specify the exact inventory and documentation
extraction checklist, recovery-reference names, safe handling of dirty files,
test commands, integration order and rollback procedure. These are implementation
details; they do not waive the preservation, privacy or acceptance criteria above.
