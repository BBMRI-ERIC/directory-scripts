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

### Scoped Pydantic validation

Pydantic is used narrowly in this repository.

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

- `checks/FactTables.py`
  - runtime QC warning producer
  - uses the shared helper logic to avoid reporting known deterministic false positives

- `collection-factsheet-descriptor-updater.py`
  - explicit maintenance CLI
  - uses the same shared helper logic to propose and optionally apply descriptor updates to staging-area `Collections`

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
  - maps `check ID -> entity ID`
  - used only to hide known residual false positives from QC output
- `warning_suppressions.py`
  - loader/normalizer for the suppression JSON
- `warningscontainer.py`
  - applies suppressions before warnings are written to stdout/XLSX

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

## Withdrawal scope

Directory-backed tools exclude withdrawn biobanks/collections by default.

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
