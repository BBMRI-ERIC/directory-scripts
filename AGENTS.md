# Repository Guidelines

## Project Structure & Module Organization
- Top-level Python scripts drive validation and exports (for example `data-check.py`, `exporter-*.py`, `full-text-search.py`).
- `checks/` contains Yapsy plugin checks (`*.py` + `*.yapsy-plugin`) loaded by `data-check.py`.
- `data-check-cache/` and `indexdir/` are runtime caches/indexes; they can be purged with command flags.
- Reference/config artifacts live at the repo root (for example `requirements.txt`, `geocoding.config`, `en_product1.xml`).

## Build, Test, and Development Commands
- `python3 data-check.py` runs the default validation suite.
- `python3 data-check.py --purge-all-caches -X results.xlsx` clears all caches and writes an XLSX report.
- `python3 data-check.py -v --purge-cache directory -N -X results.xlsx` verbose run, directory cache only, XLSX only.
- `python3 data-check.py -O en_product1.xml` enables ORPHA-to-ICD checks (requires the XML file).
- `./full-text-search.py 'term'` performs Whoosh-based directory search; see `README.md` for examples.

## Coding Style & Naming Conventions
- Python 3 scripts with 4-space indentation and PEP 8-inspired layout; keep existing vim modelines intact.
- Prefer `snake_case` for variables/functions and short, descriptive script names; follow existing `exporter-*.py` and `data-check.py` naming patterns.
- Keep scripts runnable as standalone CLIs with argparse flags and clear help text.

## Design Principles
- `directory.py` is the single abstraction for Directory API access. Keep it lean, well documented, and the sole location for shared API calls.
- Modularize cross-cutting concerns into focused helpers (for example `warningscontainer.py`, `customwarnings.py`, `star-model.py`, `nncontacts.py`, `orphacodes.py`).
- Avoid duplicating API logic in scripts; import and reuse the shared modules instead.

## Modularization Guidelines
- Keep exporters thin: CLI + orchestration only; move reusable logic into helper modules.
- Keep all the logic of BBMRI-ERIC Directory and Molgenis access confined into the directory.py module and enrich this as needed to have it universally reusable
- Group related logic by concern (mappings in `orphacodes.py`/`icd10codeshelper.py`, warnings in `warningscontainer.py`/`customwarnings.py`, dataframe shaping in `pddfutils.py`).
- Share common parsing/formatting (e.g., email parsing, ID/NN extraction) through utilities rather than reimplementing in multiple scripts.
- Keep domain-specific analytics in dedicated exporter scripts; if reused by multiple exporters, extract to a module with a clear API.
- Prefer pure functions for computations; keep I/O (Directory access, XLSX read/write) at script boundaries.

## Exporters: Development, Deployment & Documentation
- Exporters are the `exporter-*.py` scripts (for example `exporter-all.py`, `exporter-country.py`, `exporter-diagnosis.py`, `exporter-quality-label.py`).
- New exporters should read data via `directory.py`, accept CLI arguments, and keep output schemas stable.
- Deployment: treat exporters as runnable CLIs; document required credentials, input files, output locations, and expected file formats (CSV/XLSX/XML/JSON).
- For each exporter, document the exact command line used in production (including flags, package, and cache settings) and where outputs are published or uploaded.
- If deployed on a schedule, record the trigger (cron/job name), environment (host/container), and any required secrets or config files.
- When outputs are consumed downstream, document the consumer, schema version, and any stability guarantees.
- Document each exporter in `README.md` with purpose, required inputs, and example usage/output.
- Prefer small, composable helpers over copy-pasted query logic; factor common code into modules.

## Operational Notes
- XLSX inputs are typically read with pandas; ensure `openpyxl` is installed for `read_excel` compatibility.
- Directory API access requires network access; account for this when running in sandboxed environments.
- When deriving NN from IDs, the common pattern is `ID:XX_...` (XX can be multi-letter like `EXT`).
- `directory-tables-modifier.py` requires an explicit schema (`-s/--schema`) and treats table deletion as content deletion only (no dropping tables).
- For `directory-tables-modifier.py`, prefer explicit `--import-table`; CSV/TSV format is auto-detected but can be overridden with `--import-format`/`--delete-format`/`--export-format`.
- `directory-tables-modifier.py` supports `--national-node` to populate missing `national_node` values on import; warn if the column already exists in the input.
- Data-changing operations in `directory-tables-modifier.py` require interactive confirmation unless `-f/--force` is used; `-n/--dry-run` previews changes without writing; `-q/--quiet` suppresses non-error output.
- Facts tooling in `directory-tables-modifier.py` supports export and deletion with filters (`--fact-id-regex`, `--collection-id`) and should always be documented in `README.md` with examples.
- Negotiator orphans logic: output includes all input rows; `auto_by_biobank` applies only when a biobank has at least two collections with identical representative sets; `auto_by_parent` uses the nearest non-withdrawn parent with reps; withdrawn collections/biobanks in output are logged as warnings. Q-labels use `getQualColl()`/`getQualBB()` only (no `combined_quality` propagation).
- XLSX schema note (`exporter-negotiator-orphans.py`):
  - `nn_summary` includes “Number of biobanks without collections” (count of active biobanks with `total_collections == 0`), positioned with other biobank-related columns.
  - `biobanks_summary` includes `total_collections` and now includes active biobanks even if they have 0 collections.

## Testing Guidelines
- No dedicated unit test suite is present; validation is primarily exercised via `data-check.py`.
- When adding a check, include a `checks/<Name>.py` plugin and matching `checks/<Name>.yapsy-plugin`.
- Use targeted runs with `--disable-plugins` and cache flags to validate new checks efficiently.
- Cache guidance for local testing: avoid `--purge-cache directory` unless you suspect recent Directory content changes may affect results; prefer reusing the existing cache to keep comparisons stable and runs faster.

## Commit & Pull Request Guidelines
- Commit messages are short, present-tense summaries (for example “Adapted exporter-quality-label.py…” or “updates”) and should include a comprehensive description of changes in the commit message body.
- For PRs, include a concise description, the command(s) run, and attach or reference generated artifacts (such as XLSX reports) when relevant.
- Link related issues/tickets when available and call out any cache or data dependencies.

## Documentation Expectations
- Maintain and expand documentation alongside code changes; updates are required for new checks, exporters, or API changes.
- Keep `README.md` accurate and add per-script usage examples as interfaces evolve.

## Security & Configuration Tips
- Keep credentials out of the repo; prefer CLI flags (`-u`, `-p`) or local config files not committed.
- For DNS-dependent checks, ensure `/etc/resolv.conf` is available as noted in `README.md`.
