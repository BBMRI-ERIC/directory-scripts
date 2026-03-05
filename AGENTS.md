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
- `python3 -m py_compile <changed-python-files>` performs a fast syntax check for touched Python files.
- `pytest -q` runs the unit test suite; use `pytest -q tests/test_directory.py` for focused `directory.py` checks.

## Coding Style & Naming Conventions
- Python 3 scripts with 4-space indentation and PEP 8-inspired layout; keep existing vim modelines intact.
- Prefer `snake_case` for variables/functions and short, descriptive script names; follow existing `exporter-*.py` and `data-check.py` naming patterns.
- Keep scripts runnable as standalone CLIs with argparse flags and clear help text.
- For reusable modules and public APIs, keep class/method/function docstrings complete and consistent (one style per file, e.g. Google-style).

## Design Principles
- `directory.py` is the single abstraction for Directory API access. Keep it lean, well documented, and the sole location for shared API calls.
- Modularize cross-cutting concerns into focused helpers (for example `warningscontainer.py`, `customwarnings.py`, `star-model.py`, `nncontacts.py`, `orphacodes.py`).
- Avoid duplicating API logic in scripts; import and reuse the shared modules instead.
- Use assertive runtime validation for assumptions that depend on input/data/configuration; raise clear exceptions instead of relying on `assert` for runtime safety.
- `nncontacts.py` is the single source of truth for BBMRI node contacts, member-node classification, staging-area parsing, and non-member/global area detection; do not re-encode that logic elsewhere.
- Keep permitted non-country staging prefixes (currently `EXT`, `EU`, `IARC`) and staging-prefix-to-schema expectations in `nncontacts.py`; checks and tools such as `ValidateIDs` and `collection-factsheet-descriptor-updater.py` must use that shared configuration rather than hardcoding `EXT` rules locally.

## Modularization Guidelines
- Keep exporters thin: CLI + orchestration only; move reusable logic into helper modules.
- Keep all the logic of BBMRI-ERIC Directory and Molgenis access confined into the directory.py module and enrich this as needed to have it universally reusable
- Group related logic by concern (mappings in `orphacodes.py`/`icd10codeshelper.py`, warnings in `warningscontainer.py`/`customwarnings.py`, dataframe shaping in `pddfutils.py`).
- Share common parsing/formatting (e.g., email parsing, ID/NN extraction) through utilities rather than reimplementing in multiple scripts.
- Keep domain-specific analytics in dedicated exporter scripts; if reused by multiple exporters, extract to a module with a clear API.
- Prefer pure functions for computations; keep I/O (Directory access, XLSX read/write) at script boundaries.
- In checks with multiple entity loops or second-pass validation, reinitialize all loop-local derived variables inside each loop. Do not rely on values computed in a previous loop iteration or a previous entity pass; this caused real bugs in `checks/COVID.py`.
- When a check is meant to validate collection-level fields, iterate collections, not biobanks or another nearby entity type; this caused a real bug in `checks/CheckURLs.py`.
- When building warning messages/actions from related entities, derive the referenced entity explicitly in the local scope instead of relying on a nearby variable name; this caused a real bug in `checks/OrphanedCollections.py`.
- Be careful with the positional `DataCheckWarning(...)` signature: keep the `directoryEntityWithdrawn` argument in place before `message`/`action`, otherwise warnings silently shift fields; this caused a real bug in `checks/AccessPolicies.py`.

## Exporters: Development, Deployment & Documentation
- Exporters are the `exporter-*.py` scripts (for example `exporter-all.py`, `exporter-country.py`, `exporter-diagnosis.py`, `exporter-quality-label.py`).
- New exporters should read data via `directory.py`, accept CLI arguments, and keep output schemas stable.
- Importer/synchronizer scripts such as `importer-ecrin-mdr.py` and `sync_directory_with_fdp.py` may target external systems and are not normal exporters; keep their authentication optional when the CLI/env input is optional, and preserve their authorship/acknowledgement headers when editing them.
- Deployment: treat exporters as runnable CLIs; document required credentials, input files, output locations, and expected file formats (CSV/XLSX/XML/JSON).
- For each exporter, document the exact command line used in production (including flags, package, and cache settings) and where outputs are published or uploaded.
- If deployed on a schedule, record the trigger (cron/job name), environment (host/container), and any required secrets or config files.
- When outputs are consumed downstream, document the consumer, schema version, and any stability guarantees.
- Document each exporter in [`README.md`](README.md) with purpose, required inputs, and example usage/output.
- Prefer small, composable helpers over copy-pasted query logic; factor common code into modules.

## Operational Notes
- XLSX inputs are typically read with pandas; ensure `openpyxl` is installed for `read_excel` compatibility.
- Directory API access requires network access; account for this when running in sandboxed environments.
- When deriving NN from IDs, the common pattern is `ID:XX_...` (XX can be multi-letter like `EXT`).
- Staging area and country are not the same concept: non-member/global areas such as `EXT` or `EU` can host entities whose `country` is a BBMRI member state.
- `Directory.get*NN(...)` is for node/staging-area routing and grouping and must follow entity IDs via `nncontacts.py`; `Directory.get*Country(...)` is for reported country values. For example, `US`/`VN` biobanks in `EXT` belong under the `EXT` node tab, not country-specific tabs.
- `directory-tables-modifier.py` requires an explicit schema (`-s/--schema`) and treats table deletion as content deletion only (no dropping tables).
- `collection-factsheet-descriptor-updater.py` analyzes facts from `ERIC` but writes only to the explicitly requested staging-area schema; it must confirm schema/prefix mismatches interactively unless `-f/--force` is used.
- `collection-factsheet-descriptor-updater.py` intentionally reads the public `ERIC` schema without authentication and uses credentials only for the staging-area write session; do not treat missing ERIC read credentials as a bug in reviews unless the operating model changes.
- `collection-factsheet-descriptor-updater.py` should only append missing multi-value descriptors by default; only `--replace-existing` may remove/replace existing diagnosis/material/sex values, while all-star sample/donor totals may still replace numeric totals without that option.
- `collection-factsheet-descriptor-updater.py` must treat fact-sheet `*` rows as aggregates only and must not propagate `NAV` sample type to collection metadata when other fact/metadata material types exist.
- `collection-factsheet-descriptor-updater.py` age proposals must span the full min..max range represented in the fact sheet when one consistent unit is available, even if the fact sheet contains holes between age buckets.
- `data-check.py --export-update-plan ...` exports structured fix proposals attached to warnings; `qcheck-updater.py` consumes that plan instead of recomputing QC logic independently.
- exported QC fix-plan `module` values must match the visible QC check-prefix family seen by users (`AP`, `CC`, `C19`, `FT`, `TXT`); keep semantic detail in `update_id`, not in a second competing module naming scheme.
- Structured QC fix proposals must carry human-readable explanations, expected current values, confidence (`certain`, `almost_certain`, `uncertain`), and any validated ontology-term explanations needed for user review.
- `qcheck-updater.py` must reuse `.env` (`DIRECTORYTARGET`, `DIRECTORYUSERNAME`, `DIRECTORYPASSWORD`) consistently with the other write-capable tools.
- `qcheck-updater.py` must support exact-entity, hierarchy-root, staging-area, check-id, update-id, module, and confidence filtering; the hierarchy can be biobank->collections or collection->subcollections, but not contact-sharing relationships.
- `qcheck-updater.py` must support a human-readable `--list` mode for inspecting updates without applying them.
- `qcheck-updater.py` dry runs must execute the same interactive per-update review logic as real applies and differ only in skipping the final write to the Directory.
- `qcheck-updater.py` live-value mismatches against `expected_current_value` must be handled per update during interactive review; declining one mismatched update must skip only that update, not abort the whole run.
- `qcheck-updater.py` must compare unordered multi-value fields canonically; pure reordering of `data_use`, `type`, `diagnosis_available`, `materials`, or `sex` must not trigger false mismatches.
- `qcheck-updater.py` supports CollectionFacts row-deletion fixes (`mode=delete_rows`, field `facts`) for collection-scoped updates such as `FT:KAnonViolation`; these must delete only the explicitly proposed fact row IDs and remain no-op-safe when rows are already absent.
- `qcheck-updater.py` review output for append updates must show both the final target value and the incremental addition, not a replacement-looking payload.
- DUO term comparison must normalize `DUO_0000000` and `DUO:0000000` forms so already-present terms are not proposed again under a different separator.
- Equivalent ontology-term storage forms that are already present in live data must be treated as no-op updates, not as additions requiring user approval.
- Fact-sheet/QC fix rationales must stay field-specific; age caveats must not leak into diagnosis or other unrelated update rationales.
- Checksums on exported QC update plans are advisory integrity markers: warn on mismatch, but keep an override path so deliberate user edits of the JSON plan remain possible.
- QC-derived updates are only appropriate when the node edits the Directory staging area directly. If the staging area is synchronized/imported from another authoritative system, fixes must be made in that primary source instead.
- All other Directory-backed scripts default to schema `ERIC`; use `-P/--schema` only when you intentionally want a different staging area.
- For `data-check.py` and other read/check tools, non-`ERIC` schema access must authenticate first and only then select the schema; missing credentials for a non-`ERIC` schema should fail as a user-facing configuration error rather than as a low-level schema exception.
- For `directory-tables-modifier.py`, use explicit `-T/--table`; CSV/TSV format is auto-detected but can be overridden with `-F/--file-format`, and field separator can be overridden with `-S/--separator` (for example `;`).
- `directory-tables-modifier.py` supports `--national-node` to populate missing `national_node` values on import; warn if the column already exists in the input.
- `directory-tables-modifier.py` supports CollectionFacts k-anonymization filters during import/sync: `-k/--k-donors` for `number_of_donors < k` and `-K/--k-samples` for `number_of_samples < k`; report skipped-row counts and keep this limited to `-T CollectionFacts`.
- Recommended baseline for public Directory fact data is donor `k=10`; exceptions are possible for documented pre-anonymized collections/pipelines.
- Data-changing operations in `directory-tables-modifier.py` require interactive confirmation unless `-f/--force` is used; `-n/--dry-run` previews changes without writing; `-q/--quiet` suppresses non-error output.
- `directory-tables-modifier.py` should normally target node staging areas, not `ERIC`; if `ERIC` is explicitly requested, the script must require an extra confirmation unless `-f/--force` is used.
- Table tooling in `directory-tables-modifier.py` supports export and deletion with filters (`--id-regex`, `--collection-id`) and should always be documented in `README.md` with examples.
- `directory-tables-modifier.py` sync mode (`-y/--sync-data`) is server-non-atomic (full-table uses truncate+import; filtered scope uses delete+import), but the script must create a temporary full-column backup of the sync scope and attempt rollback automatically when sync import fails.
- For CLI help consistency, keep standard options first and in stable order: `-h`, `-v`, `-d`, then Directory auth/target options, then tool-specific options.
- Negotiator orphans logic: output includes all input rows; `auto_by_biobank` applies only when a biobank has at least two collections with identical representative sets; `auto_by_parent` uses the nearest non-withdrawn parent with reps; withdrawn collections/biobanks in output are logged as warnings. Q-labels use `getQualColl()`/`getQualBB()` only (no `combined_quality` propagation).
- XLSX schema note (`exporter-negotiator-orphans.py`):
  - `nn_summary` includes “Number of biobanks without collections” (count of active biobanks with `total_collections == 0`), positioned with other biobank-related columns.
  - `biobanks_summary` includes `total_collections` and now includes active biobanks even if they have 0 collections.
- `directory-stats.py` sorting rule: normal output is lexicographic by biobank ID; pure `EXT` views are sorted by `country` first and then by ID.
- QC CLI note: `data-check.py` and other QC tools using `cli_common.add_remote_check_disable_arguments(...)` expose `-r` / `--disable-checks-all-remote`.
- Directory-backed tools and exporters exclude withdrawn biobanks/collections by default; `-w` / `--include-withdrawn` includes them and `--only-withdrawn` restricts the run to them.
- `full-text-search.py` keeps separate index directories per schema and withdrawn scope; do not mix those caches manually.
- Reviewed false positives belong in `warning-suppressions.json` as `check ID -> entity ID` suppressions. Prefer fixing deterministic logic first; use suppressions only for known residual false positives.
- Withdrawal for checks is logically inherited for collections: a collection counts as withdrawn if it is withdrawn itself, if its biobank is withdrawn, or if an ancestor collection is withdrawn.
- AI-assisted findings that should be shareable belong in `ai-check-cache/`, not in private runtime caches such as `data-check-cache/`.
- `ai-check-cache/` stores reviewable JSON findings committed to Git; regular `data-check.py` runs only read those findings and must not require live model access.
- Regex-like or heuristic text checks belong in deterministic plugins such as `TextConsistency`, not in `ai-check-cache/`.
- Current AI-reviewed domains include access-governance metadata gaps, participant phenotypic/clinical-profile gaps, data-category gaps, and material-metadata gaps.
- AI cache reuse is checksum-based: findings remain reusable only while the live entity checksum and source-field checksum still match; `AIFindings` logs script warnings listing changed entity IDs and skips stale findings until the live AI-review workflow refreshes the cache.
- AI cache checksums must exclude pure runtime metadata such as timestamps and `mg_*` fields so metadata-only churn does not force pointless reruns.
- `exporter-bbmri-cohorts.py` uses `-W/--warnings`; keep `-w` reserved for withdrawn-scope selection.
- Scoped local validation is intentionally limited to local tool settings and repository-owned JSON/cache artifacts; do not wrap full live Molgenis payloads with strict models.
- Non-fatal validation issues from local config/cache parsing should become suppressible script warnings (`--suppress-validation-warnings`), not hard crashes; use hard input errors only when a tool cannot proceed safely.
- Directory caches are partitioned by schema (`directory-ERIC`, `directory-BBMRI-EU`, ...) but not by target URL; if a task intentionally switches to a non-default Directory instance, document the remaining cache-sharing risk and purge the schema-specific `directory` cache when switching targets.
- Quality-info tables are optional outside `ERIC`; shared tooling should skip them gracefully on schemas that do not expose `QualityInfoBiobanks` or `QualityInfoCollections`.
- For fact-sheet material alignment, NAV-only fact output is ambiguous because k-anonymity suppression can hide richer material-specific rows; document that ambiguity instead of treating NAV-only facts as definitive evidence that richer collection metadata is wrong.

## Testing Guidelines
- A pytest-based unit test suite is present in `tests/` (currently focused on reusable modules such as `directory.py`).
- Run unit tests with `pytest -q` (or targeted subsets with `pytest -q tests/test_directory.py`).
- For live cache behavior in `directory.py`, run `pytest -q tests/test_directory_live_cache_modes.py --live-directory --live-directory-mode both` (or `cached` / `fresh`).
- Live tests accept `--live-directory-schema` (or env `DIRECTORY_TEST_SCHEMA`) and optional env credentials `DIRECTORYUSERNAME` / `DIRECTORYPASSWORD`.
- Live cache-mode tests execute in an isolated temporary working directory to avoid purging the regular local cache.
- Install test dependencies with `pip3 install -r requirements-test.txt` when needed.
- When adding a check, include a `checks/<Name>.py` plugin and matching `checks/<Name>.yapsy-plugin`.
- Use targeted runs with `--disable-plugins` and cache flags to validate new checks efficiently.
- Cache guidance for local testing: avoid `--purge-cache directory` unless you suspect recent Directory content changes may affect results; prefer reusing the existing cache to keep comparisons stable and runs faster.
- For `directory-stats.py` changes, keep cross-checks against other exporters where totals overlap, especially `exporter-all.py`.
- When changing `nncontacts.py`, verify both warning routing and any staging/member-area classification tests.
- When changing fact-sheet descriptor alignment logic, validate both `checks/FactTables.py` and `collection-factsheet-descriptor-updater.py` because they intentionally share comparison/derivation rules.
- When changing structured QC fix proposals, validate both `data-check.py --export-update-plan ...` and `qcheck-updater.py`, because the warning emission and updater apply path must stay aligned.
- When changing check documentation metadata or manual extraction, test both the local plugin tests and `../BBMRI-ERIC-Directory-Data-Manager-Manual/scripts/generate_checks_docs.py`.

## Quality Gate
- Use `skills/assertive-quality-gate/SKILL.md` as a required gate before every push.
- Also apply the same gate when user asks to review code or test code.
- Use `skills/propose-ai-checks/SKILL.md` only when the user explicitly asks to review current data and propose new AI checks.
- Use `skills/run-ai-checks/SKILL.md` when running full AI-model review on live data, refreshing `ai-check-cache/`, or validating stale AI-cache warnings.
- Use `skills/review-check-redundancy/SKILL.md` before committing or pushing changes to `checks/`, `text_consistency.py`, `checks/AIFindings.py`, `ai_cache.py`, or `ai-check-cache/`.
- Prioritize reusable modules (especially `directory.py`) for defensive checks, docstrings, and regression tests.
- If `checks/` changes, verify `make_check_id(...)` identifiers are meaningful and `DataCheckWarning(...)` messages are actionable.
- For new or changed checks, keep machine-readable `CHECK_DOCS` metadata next to the implementation when the check has non-obvious business context, and keep severity/entity/field declarations aligned with emitted `DataCheckWarning(...)` calls.
- `CHECK_DOCS` must be written as complete manual-facing documentation, not just as extracted-code hints: provide concrete `fields`, a clean generic `summary`, and a practical `fix` whenever the warning text is dynamic, partial, or emitted from helper logic that the AST extractor cannot follow.
- `CHECK_DOCS.fields` may use explicit cross-entity references such as `CONTACT.email` or `BIOBANK.country` when a check depends on linked data from another entity; prefer that over pretending the dependency is local to the warning entity.
- If a check is backed by `ai-check-cache/`, keep the plugin implementation and the JSON findings aligned: the plugin defines the stable runtime warning ID (`AI:Curated`), while the JSON files carry the concrete entity-level findings and evidence.
- `AIFindings` supports both collection-level and biobank-level AI-reviewed findings; keep the cached `entity_type` aligned with the real target entity.
- New AI-check proposals must review existing deterministic checks and existing `ai-check-cache/` findings first; prefer deterministic checks when the rule can be stated clearly and tested robustly.
- AI-check work is always two-step: first proposal with real-data counts and overlap analysis, then implementation only after explicit user approval.
- Proposal/review of AI checks must use the strongest available model in the current session; if that is not the strongest model available, tell the user before relying on the review.
- After changing deterministic text heuristics, rerun the relevant plugin/tests and the normal QC path; after changing AI cache content, rerun the live AI-review workflow, inspect the refreshed AI findings, and then rerun the relevant tests plus the normal QC path before committing.
- Do not assume that adding `CHECK_DOCS` alone is enough; after changing check documentation metadata, verify the rendered/manual-facing result through `../BBMRI-ERIC-Directory-Data-Manager-Manual/scripts/generate_checks_docs.py` and inspect the generated `checks-doc.tex` / `CHECKS.md` output for the affected checks.
- Member-area consistency logic is subtle: member-country institutions may appear only in non-member areas as a reviewed exception, but the same institution must not be duplicated across member and non-member/global areas; `EU` is only an exception for hosting location, not for duplicate institutions.

## Commit & Pull Request Guidelines
- Commit messages are short, present-tense summaries (for example “Adapted exporter-quality-label.py…” or “updates”) and should include a comprehensive description of changes in the commit message body.
- For PRs, include a concise description, the command(s) run, and attach or reference generated artifacts (such as XLSX reports) when relevant.
- Link related issues/tickets when available and call out any cache or data dependencies.

## Documentation Expectations
- Maintain and expand documentation alongside code changes; updates are required for new checks, exporters, or API changes.
- Keep [`README.md`](README.md) accurate and add per-script usage examples as interfaces evolve.
- If a change also affects the Directory Data Manager manual tooling, update the corresponding files in `../BBMRI-ERIC-Directory-Data-Manager-Manual/` as a coordinated follow-up; that repo contains the check-documentation generator and is not updated automatically by changes here.
- When `CHECK_DOCS.fields` differ from AST-extracted fields by design, document the real intended fields explicitly and validate that the manual generator uses the documented fields rather than falling back to `None explicitly detected`.
- When updating `AGENTS.md` itself: adding new knowledge is allowed directly; removing existing knowledge or merging/consolidating it with older guidance requires explicit human-in-the-loop approval.

## Security & Configuration Tips
- Keep credentials out of the repo; prefer CLI flags (`-u`, `-p`) or local config files not committed.
- For DNS-dependent checks, ensure `/etc/resolv.conf` is available as noted in `README.md`.
- `directory.py` debug logs may intentionally include username/password for private troubleshooting; never share or commit such logs.
- In `checks/ContactFields.py`, static placeholder-domain checks (for example `example.org`, `test.com`, `unknown.*`) must remain active even when remote email checks are disabled; `--disable-checks-all-remote` only suppresses MX/reachability validation, not local syntax or placeholder checks.
