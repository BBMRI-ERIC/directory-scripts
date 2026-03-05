# Development Notes

This document collects developer-facing architecture, code-organization, style, and testing guidance that does not belong in the user-focused `README.md`.

For user-facing usage, installation, and tool examples, see [README.md](README.md).

## Architecture

### Repository structure

- Top-level scripts are CLIs for validation, export, search, and maintenance.
- `checks/` contains Yapsy plugins only. Files there should be warning-producing checks, plus their matching `*.yapsy-plugin` descriptors.
- Reusable infrastructure belongs outside `checks/` in top-level helper modules.

### Core module boundaries

- `directory.py`
  - single shared abstraction for Directory / Molgenis access
  - owns shared data retrieval, schema handling, withdrawal scoping, and graph helpers
- `checks/`
  - owns actual QC logic that emits `DataCheckWarning(...)`
- helper modules such as `nncontacts.py`, `warningscontainer.py`, `warning_suppressions.py`, `orphacodes.py`, `oomutils.py`, `text_consistency.py`, `fact_descriptor_sync.py`
  - own reusable logic that can be consumed by multiple scripts or plugins

### Directory cache scope

- The shared `data-check-cache/directory` cache is keyed by entity class/table, not by target URL.
- This is acceptable for the current operating model, but it means alternate Directory targets share the same cache namespace.
- When switching a tool to a non-default Directory instance, purge the `directory` cache before switching back or comparing runs across targets.

### Scoped local validation

A lightweight in-repo validation layer is used narrowly in this repository.

- Use it for local inputs and repository-owned artifacts:
  - tool/runtime settings
  - shareable AI-cache payloads
  - warning-suppression JSON
- Do not use it as a full wrapper around live Molgenis Directory entities.
  - Molgenis already enforces much of the structural validity for stored data.
  - wrapping the whole live payload graph would add brittleness and duplicate validation noise.
- Non-fatal validation problems must not crash the tool:
  - QC path: log script-level validation warnings and continue
  - maintenance CLIs: raise user-facing input errors only when the tool cannot proceed safely
- Validation warnings should be suppressible via `--suppress-validation-warnings` where supported.

### Deterministic text checks vs AI-reviewed findings

Narrative-vs-structure checks are split into two categories:

- Deterministic checks
  - implemented directly as plugins
  - current example: `checks/TextConsistency.py`
  - use regexes / heuristics / explicit code logic
  - run directly on live Directory data during `data-check.py`
  - emit stable deterministic IDs such as:
    - `TXT:AgeRange`
    - `TXT:StudyType`
    - `TXT:FFPEMaterial`
    - `TXT:CovidDiag`

- AI-reviewed findings
  - stored in `ai-check-cache/`
  - reserved only for findings that genuinely need full AI-model review on live data and cannot be expressed robustly as deterministic logic
  - emitted at runtime by `checks/AIFindings.py` as `AI:Curated`
  - current rule families cover:
    - access-governance metadata gaps
    - participant phenotypic/clinical-profile gaps
    - data-category gaps
    - material-metadata gaps

Rule of thumb:
- if a rule can be implemented with regexes, heuristics, or ordinary Python logic, it should be a deterministic plugin
- `ai-check-cache/` is only for the residual fuzzy cases

### Fact-sheet alignment helpers vs runtime checks/tools

- `fact_descriptor_sync.py`
  - shared derivation/comparison logic for collection descriptors vs fact sheets
  - used by both `checks/FactTables.py` and `collection-factsheet-descriptor-updater.py`
  - owns special handling such as:
    - ignoring `*` fact-sheet aggregate values for descriptor comparison
    - treating `NAV` material as ambiguous/non-authoritative when richer materials may be hidden by k-anonymity suppression
    - preserving broader ICD-10 metadata codes when they already cover more specific fact-sheet diagnoses

- Design note for material updates:
  - NAV-only fact output is not definitive evidence that collection-level materials are wrong.
  - Fact rows can be suppressed by k-anonymity, so richer metadata may still be valid.
  - Treat such cases as review-required and document the ambiguity clearly in user-facing tooling/docs.
- Design note for age updates:
  - preserve fact-sheet month/day/week/year units when they can be inferred consistently
  - do not auto-update age metadata when fact rows mix incompatible units
  - when facts use one consistent unit, age proposals should cover the full min..max span represented by the fact rows even if the fact table has gaps between age buckets

- `checks/FactTables.py`
  - runtime QC warning producer
  - uses the shared helper logic to avoid reporting known deterministic false positives

- `collection-factsheet-descriptor-updater.py`
  - explicit maintenance CLI
  - uses the same shared helper logic to propose and optionally apply descriptor updates to staging-area `Collections`

- `qcheck-updater.py`
  - explicit maintenance CLI for QC-derived fix plans
  - consumes structured `fix_proposals` exported from `data-check.py`
  - supports human-readable listing, dry-run, interactive apply, and forced batch apply

If descriptor-alignment logic changes, keep both the check and the updater behavior consistent.

### `ai_cache.py` vs `checks/AIFindings.py`

These two files serve different layers:

- `ai_cache.py`
  - helper/infrastructure module
  - loads JSON files from `ai-check-cache/`
  - validates payload structure
  - computes and compares checksums
  - reports stale-cache issues back to the caller
  - does not emit `DataCheckWarning(...)` itself

- `checks/AIFindings.py`
  - actual Yapsy plugin
  - consumes `ai_cache.py`
  - turns cache records into runtime `DataCheckWarning(...)`
  - logs script warnings when cache entries are stale
  - supports both `COLLECTION` and `BIOBANK` AI-reviewed findings
  - owns the manual-facing `CHECK_DOCS` for the cache-backed check

So:
- `ai_cache.py` is infrastructure
- `checks/AIFindings.py` is a check

That is why `ai_cache.py` stays outside `checks/`.

### Check documentation metadata

Checks can carry machine-readable `CHECK_DOCS` metadata directly in plugin source.

Use `CHECK_DOCS` for:
- developer/manual-facing summaries
- explicit field declarations
- business-context explanations that cannot be reconstructed reliably from AST parsing alone

Keep `CHECK_DOCS` aligned with the emitted `DataCheckWarning(...)` calls.

### Warning suppressions

- `warning-suppressions.json`
  - reviewed false-positive suppressions
  - supports legacy map format and structured v2 list format with metadata
  - canonical v2 fields: `check_id`, `entity_id`, optional `entity_type`, `reason`, `added_by`, `added_on`, `expires_on`, `ticket`
  - suppression keys may match either warning IDs (`FT:KAnonViolation`) or module/update IDs exported in fix plans (`FT/facts.k_anonymity.drop_rows_k10`)
  - used only to hide known residual false positives from QC output
- exported QC update-plan JSON
  - checksum-signed fix-plan artifact produced by `data-check.py -U/--export-update-plan ...`
  - consumed by `qcheck-updater.py`
  - carries both per-update integrity checksums and expected current field values
  - omits fix proposals that match configured warning suppressions
- `warning_suppressions.py`
  - loader/normalizer for suppression JSON
  - provides diagnostics for unknown check IDs, stale entity IDs, and expired suppressions
- `warning-suppressions-manage.py`
  - CLI for add/list/validate/prune-stale management of suppression entries
- `warningscontainer.py`
  - applies suppressions before warnings are written to stdout/XLSX
  - debug mode can print suppressed warning details for runtime traceability

Suppressions are not a substitute for fixing deterministic logic. Prefer code fixes first; keep suppressions for reviewed residual cases.

After changing check docs metadata, validate with:

```bash
python3 ../BBMRI-ERIC-Directory-Data-Manager-Manual/scripts/generate_checks_docs.py
```

## Coding Style

- Python 3, 4-space indentation, keep existing vim modelines intact.
- Prefer `snake_case` names and small reusable helpers.
- Keep exporters thin: CLI + orchestration only.
- Keep shared Directory logic in `directory.py`.
- Put cross-cutting reusable logic in helper modules, not duplicated across scripts.
- Keep CLI help output consistent across scripts: standard options first (`-h`, `-v`, `-d`, then Directory target/auth options), then tool-specific options.
- Use explicit runtime validation for assumptions that depend on input/data/config.
- Prefer clear exceptions and actionable messages over silent fallback.
- For reusable/public Python APIs, keep docstrings complete and consistent.

## Testing

### Fast checks

```bash
python3 -m py_compile <changed-python-files>
pytest -q
```

### Focused tests

Examples:

```bash
pytest -q tests/test_directory.py
pytest -q tests/test_text_consistency.py tests/test_text_consistency_check.py
pytest -q tests/test_ai_cache.py tests/test_ai_findings_check.py
```

### Live Directory tests

```bash
pytest -q tests/test_directory_live_cache_modes.py --live-directory --live-directory-mode both
```

Optional live settings:
- `--live-directory-schema <SCHEMA>`
- env `DIRECTORY_TEST_SCHEMA`
- env `DIRECTORYUSERNAME`
- env `DIRECTORYPASSWORD`

### When changing checks

At minimum, run:

```bash
pytest -q tests/test_check_docs_metadata.py
python3 ../BBMRI-ERIC-Directory-Data-Manager-Manual/scripts/generate_checks_docs.py
```

If deterministic text checks changed, also run:

```bash
pytest -q tests/test_text_consistency.py tests/test_text_consistency_check.py
```

If AI cache handling changed, also run:

```bash
pytest -q tests/test_ai_cache.py tests/test_ai_findings_check.py
```

## AI review workflow

Use the Codex skill `run-ai-checks` when you need full AI-model review of live data.

That workflow should:
- use the strongest available model
- review live current data
- avoid duplicating deterministic checks
- update `ai-check-cache/` only for genuinely AI-only findings
- keep checksum metadata current
- re-run the normal QC path after cache updates

Typical follow-up validation:

```bash
python3 data-check.py -N | rg 'AI:Curated'
```

## QC-derived update workflow

- `DataCheckWarning` may carry structured `fix_proposals` alongside the human warning text.
- `data-check.py -U/--export-update-plan ...` serializes those proposals into a JSON fix plan.
- `qcheck-updater.py` reads that file, filters it, lists it in a human-readable form, and can dry-run or apply the updates to a staging schema.
- Dry-run must follow the same interactive per-update review path as a real apply; the only behavioral difference is that it stops before `save_table(...)`.
- The updater is intentionally a consumer of exported QC evidence, not a second implementation of the QC logic.
- The current updater apply path supports collection-scoped fixes: collection metadata updates in `Collections` and explicit row deletions in `CollectionFacts` (for example k-anonymity cleanup). Keep biobank/contact/network fixes out of the apply path until there is explicit support for them.
- Current default QC baseline for fact-row donor k-anonymity is `k=10` (`FT:KAnonViolation`) for public aggregated data; any lower/waived threshold should be an explicitly documented exception (for example pre-anonymized source data).
- `--list` is the non-writing inspection mode and should use the same canonical multi-value formatting as interactive review so order-only differences are not presented as live mismatches.
- Checksums are advisory integrity markers: warn on mismatch, but keep an override path so deliberate user edits remain possible.
- Every update also carries `expected_current_value`; apply logic must compare it with the live staging-area value and warn before writing when the values diverge.
- In interactive mode, expected-current-value mismatches must be handled per update during review; declining one mismatched proposal must not abort unrelated updates.
- Unordered multi-value fields must be compared canonically; order-only differences in `data_use`, `type`, `diagnosis_available`, `materials`, or `sex` are not meaningful.
- Review output must show the real effect of append updates: the final target value plus the incremental addition, not a replacement-looking payload.
- `uncertain` proposals are still exported because they can represent genuine alternative curator choices; do not auto-merge or auto-apply them blindly.
- Ontology-backed fixes such as DUO terms must carry explanations validated against the official ontology source during development; do not improvise ontology descriptions at runtime.
- DUO terms must be normalized across `DUO_0000000` and `DUO:0000000` forms before comparison and duplicate detection.
- This workflow only makes sense when the staging area is the authoritative editable source. If a node imports/synchronizes data from another primary system, fix that primary source instead.

### Current fix-producing module labels

- exported `module` values intentionally match the visible QC check-prefix family that users see in warning IDs
- current labels:
  - `AP`
    - DUO/access-policy proposals from `checks/AccessPolicies.py`
  - `CC`
    - collection-content/type fixes from `checks/CollectionContent.py`
  - `C19`
    - COVID-specific fixes from `checks/COVID.py`
  - `FT`
    - fact-sheet-derived diagnosis/material/sex/age/count fixes from `checks/FactTables.py`
  - `TXT`
    - deterministic narrative-to-structure fixes from `checks/TextConsistency.py`
- keep the semantic category in `update_id`; do not overload `module` with a second naming scheme
- keep field-specific rationale specific: notes from one domain (for example age-range caveats) must not leak into unrelated diagnosis/material/count proposals
- when an ontology-backed value is already present under an equivalent storage form (for example `DUO_0000007` vs `DUO:0000007`), both the checks and the updater must treat the proposal as a no-op rather than prompting for a duplicate addition

### Confidence handling

- `certain`
  - deterministic, directly implied by structured source data
- `almost_certain`
  - still deterministic, but with a small policy/curation assumption that must stay visible to the user
- `uncertain`
  - export and list these proposals, but treat them as curator-choice candidates rather than safe batch updates

### Selection and conflict handling

- Filters combine as `AND`; comma-separated/repeated values within the same filter combine as `OR`.
- Supported selectors:
  - exact entity id
  - hierarchy root id
  - staging area
  - `check_id`
  - `update_id`
  - `module`
  - `confidence`
- Use `exclusive_group` for mutually exclusive alternatives in one field; the updater must not auto-merge those proposals.
- If multiple updates for the same entity/field disagree on mode or target value, keep them as conflicts and skip automatic apply.

## Withdrawal scope

Directory-backed tools exclude withdrawn biobanks/collections by default.
Directory cache directories are schema-qualified (`directory-ERIC`, `directory-BBMRI-EU`, ...). Cache purging for `directory` must affect only the currently selected schema cache; target-URL separation is still not provided.

For `data-check.py` and similar read/check entrypoints, non-`ERIC` staging schemas must be selected only after authentication. The user-facing behavior should be:
- read credentials from CLI or `.env`
- fail early with a clear input/configuration error if a non-`ERIC` schema is requested without credentials
- authenticate first, then set the target schema, so private staging areas do not fail with a misleading low-level schema-not-found exception
- treat quality-info tables as optional for non-`ERIC` schemas and degrade to empty DataFrames instead of failing when those tables are absent

Collection withdrawal is logically inherited:
- withdrawn collection -> withdrawn
- biobank withdrawn -> all child collections treated as withdrawn
- ancestor collection withdrawn -> descendant collection treated as withdrawn

Use:
- `-w` / `--include-withdrawn` to include withdrawn content
- `--only-withdrawn` to restrict the run to withdrawn content

Node/staging-area scope and reported country must stay distinct:
- `Directory.get*NN(...)` is for BBMRI node / staging-area routing and workbook grouping, derived from entity IDs via `nncontacts.py`
- `Directory.get*Country(...)` is for actual reported country values
- non-member biobanks hosted in countries such as `US` or `VN` must still route/group under `EXT`, not under country-specific tabs
