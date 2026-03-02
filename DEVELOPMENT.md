# Development Notes

This document collects developer-facing architecture, code-organization, style, and testing guidance that does not belong in the user-focused `README.md`.

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
- helper modules such as `nncontacts.py`, `warningscontainer.py`, `orphacodes.py`, `oomutils.py`, `text_consistency.py`
  - own reusable logic that can be consumed by multiple scripts or plugins

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

Rule of thumb:
- if a rule can be implemented with regexes, heuristics, or ordinary Python logic, it should be a deterministic plugin
- `ai-check-cache/` is only for the residual fuzzy cases

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
