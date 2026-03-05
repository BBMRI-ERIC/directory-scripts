# BBMRI-ERIC Directory Validation Scripts

For developer-facing architecture, coding-style, validation, and testing notes, see [DEVELOPMENT.md](DEVELOPMENT.md).

## Requirements
- Python 3
- Runtime dependencies are listed in [`requirements.txt`](requirements.txt)
- Test-only dependencies are listed in [`requirements-test.txt`](requirements-test.txt)

## Installation
- Verify installation:  
  ```
python3 -m ensurepip
```
- Install runtime dependencies: `pip3 install -r requirements.txt`
- For test dependencies only: `pip3 install -r requirements-test.txt`
- Ensure that file `/etc/resolve.conf` exists. If it does not exist create it with the following contents:  
  ```
nameserver 8.8.8.8
```
- Download the MOLGENIS Python API library:  
  ```
pip3 install molgenis-emx2-pyclient dotenv molgenis-emx2-directory-client
```
If you run into GraphQL errors when retrieving data from the Directory, upgrade the client with:\
  ```
  pip3 install --upgrade molgenis-emx2-pyclient
  ```
- Install/update root certificates (also check install_certifi.py script)  
  ```
pip3 install --upgrade certifi
```
- If you want support for checking mappings of ORPHA codes to ICD-10 codes for RD biobanks, you need to get en_product1.xml from
  http://www.orphadata.org/cgi-bin/ORPHAnomenclature.html

- If you have Python 3.12 or higher, for the time being (December, 2024) you need a patched version of yapsy module to deal with instability in the Python - some stable components being removed from the Python core. Here is a quick howto:
     ```
     git clone https://github.com/AmeyaVS/yapsy.git
     cd yapsy/package
     python -m build
     pip install --force-reinstall dist/Yapsy-2.0.0-py3-none-any.whl
```

## Data quality checks

The simplest way to run the default validation suite is:  
```
python3 data-check.py
```

Common CLI conventions across validation/export tools:
- help output keeps standard options first, in this order when supported: `-h`, `-v`, `-d`, then Directory auth/target options, then tool-specific options
- `-v` / `--verbose` for progress logging, `-d` / `--debug` for debug logging
- `-X` / `--output-xlsx` for XLSX output when the script supports workbook export
- `-N` / `--no-stdout` to suppress normal stdout output
- `--suppress-validation-warnings` to suppress non-fatal local validation warnings where a tool supports scoped local config/cache/input validation
- `-w` / `--include-withdrawn` when a tool supports opt-in processing of withdrawn entities
- `--only-withdrawn` when a tool supports withdrawn-only processing
- `--purge-cache ...` and `--purge-all-caches` for cache purging
- `-P` / `--schema` for Directory-backed tools; normal read/export/check tools default to `ERIC`, while `directory-tables-modifier.py` always requires an explicit staging area

Cache scope is now tool-specific:
- exporters that only read the Directory expose only the `directory` cache
- `full-text-search.py` exposes `directory` and `index`
- `geocoding_2022.py` exposes `directory` and `geocoding`
- `data-check.py` keeps the full QC cache and check/plugin control surface

Directory cache entries are partitioned by schema (`data-check-cache/directory-ERIC`, `data-check-cache/directory-BBMRI-EU`, ...), but not by target URL. If you intentionally point a tool at a different Directory instance than the default public target, purge the schema-specific `directory` cache before switching back or between targets; otherwise later runs can temporarily reuse cached entities from the wrong instance.

Legacy long option spellings remain accepted where needed, but the normalized lowercase kebab-case variants are preferred in documentation and automation.

`data-check.py` excludes withdrawn biobanks and collections by default. Collection withdrawal is treated logically: a collection is considered withdrawn when it is withdrawn itself, when its biobank is withdrawn, or when one of its ancestor collections is withdrawn. Use `-w` / `--include-withdrawn` only when you explicitly want to review withdrawn content as well, or `--only-withdrawn` when you want to review only withdrawn content.

When you intentionally target a non-`ERIC` schema with `data-check.py -P/--schema`, authenticate with `-u/-p` or `.env` (`DIRECTORYUSERNAME`, `DIRECTORYPASSWORD`). Anonymous access is assumed only for the public `ERIC` schema.
Quality-info tables are optional outside `ERIC`; `data-check.py` and exporters skip them automatically when the target schema does not expose them.

The XLSX warning workbook is split into tabs by BBMRI node / staging area derived from entity IDs (`AT`, `SK`, `EXT`, `EU`, ...), not by reported country. This keeps non-member biobanks hosted in countries such as `US` or `VN` grouped under the `EXT` tab. Reported country values remain available separately where scripts explicitly report country-level statistics.

For developer-facing architecture, coding-style, AI-check, and testing notes, see [DEVELOPMENT.md](DEVELOPMENT.md).

Built-in scoped validation is intentionally limited to local inputs and repository-owned artifacts:
- tool/runtime settings for `directory-tables-modifier.py` and `collection-factsheet-descriptor-updater.py`
- shareable/local JSON artifacts such as `ai-check-cache/` payloads and `warning-suppressions.json`
- malformed local artifacts are treated as non-fatal validation warnings and can be hidden with `--suppress-validation-warnings`
- live Directory entities from Molgenis are still handled primarily through explicit runtime checks and the existing QC framework

For fact-sheet-driven descriptor updates, `NAV` sample-type rows are ambiguous: they can mean “not available”, but they can also appear because material-specific rows are suppressed by k-anonymity. Treat NAV-only fact output as requiring human review rather than as definitive proof that richer collection-level material metadata is wrong.
Age-range updates from fact sheets are also conservative: month/day/week units are preserved when they can be inferred consistently, and mixed-unit fact ranges are not auto-applied.

Email validation in `ContactFields` is split into local/static checks and optional remote checks:
- local checks always run and cover missing/invalid addresses plus placeholder domains such as `example.org`, `test.com`, and `unknown.*`
- remote checks cover MX/reachability validation and are disabled by `--disable-checks-all-remote` / `--disable-checks-remote emails`
- disabling remote checks does not suppress the local placeholder-domain or syntax checks

Known false positives can be suppressed in `warning-suppressions.json`:
- mapping is `check ID -> entity ID`
- suppressed warnings are omitted from stdout and XLSX output
- use this only for reviewed false positives; fix the check logic whenever the pattern can be expressed deterministically

Purge all caches (directory + remote checks) and output both stdout and XLSX:  
```bash
python3 data-check.py --purge-all-caches -X test_results.xlsx
```

Purge only the directory cache and output to XLSX only, with verbose logging:  
```bash
python3 data-check.py -v --purge-cache directory -N -X test_results.xlsx
```

Enable ORPHA-to-ICD checks (requires en_product1.xml):  
```bash
python3 data-check.py -O en_product1.xml
```

Debug mode with fresh caches:  
```bash
python3 data-check.py -d --purge-all-caches
```

Include withdrawn entities explicitly:  
```
python3 data-check.py -w -X withdrawn-review.xlsx
```

Run checks only on withdrawn content:  
```
python3 data-check.py --only-withdrawn -X withdrawn-only-review.xlsx
```

## Developer notes

Developer-facing architecture, coding-style, testing, and AI-check workflow notes are documented in [DEVELOPMENT.md](DEVELOPMENT.md).

OoM-based count estimation is centralized in `oomutils.py`. By default all exporters/stats that estimate counts from `order_of_magnitude` use the lower bound of the OoM interval (`10**n`). To change the policy globally, set `DIRECTORY_OOM_UPPER_BOUND_COEFFICIENT`; for example, `0.3` applies `0.3 * 10**(n+1)` consistently everywhere that OoM-based counting is used.

## Searching in the Directory

- **full-text-search.py** - full text search of the Directory using Whoosh with [Lucene search syntax](https://lucene.apache.org/core/2_9_4/queryparsersyntax.html).
  - indexes are separated by schema and withdrawn scope (`active-only`, `with-withdrawn`, `withdrawn-only`)
  - `./full-text-search.py 'bbmri-eric:ID:UK_GBR-1-101'`
  - `./full-text-search.py '"Cell therapy"~3'` (note shell escaping of quotes)
  - `./full-text-search.py '*420*'`
  - `./full-text-search.py --purge-cache directory --purge-cache index -v 'DE_*'`
  - `./full-text-search.py --only-withdrawn 'withdrawn biobank'`
  - `./full-text-search.py 'myID' | perl -ne "while(<>) {if(m/^.*?'id':\\s+'(.+?)'.*$/) {print \\$1 . \"\\n\";}}"`

## Exporters

- **exporter-all.py** - exports biobanks/collections with aggregate counts and optional filters. By default it works on active content only. Use `-w/--include-withdrawn` to include withdrawn content in the main output, `--only-withdrawn` to run only on withdrawn content, and `--output-xlsx-withdrawn` to write the withdrawn subset separately (requires `-w` or `--only-withdrawn`).  
```
python3 exporter-all.py -X all.xlsx
```
- **exporter-bbmri-cohorts.py** - BBMRI Cohorts network statistics plus warnings/errors aggregation.  
```
python3 exporter-bbmri-cohorts.py -X bbmri_cohorts_stats.xlsx -XWE bbmri_cohorts_warnings.xlsx
```
- **exporter-cohorts.py** - lists COHORT/POPULATION_BASED collections and summaries per country/biobank.  
```
python3 exporter-cohorts.py -X cohorts.xlsx
```
- **exporter-country.py** - counts biobanks/collections per country (stdout or XLSX).  
```
python3 exporter-country.py
```
- **exporter-covid.py** - COVID-related collections/biobanks with sample/donor totals.  
```
python3 exporter-covid.py -X covid.xlsx
```
- **exporter-diagnosis.py** - diagnosis inspection utility (development-focused logging).  
```
python3 exporter-diagnosis.py -d > diagnosis-exporter.log 2>&1
```
- **exporter-ecraid.py** - ECRAID-relevant collections (BSL2/3 and pathogen material) and institutions.  
```
python3 exporter-ecraid.py -X ecraid.xlsx
```
- **exporter-institutions.py** - lists juridical persons (institutions) per country.  
```
python3 exporter-institutions.py -X institutions.xlsx
```
- **exporter-mission-cancer.py** - cancer and pediatric-cancer analytics using ICD/ORPHA mapping.  
```
python3 exporter-mission-cancer.py -O en_product1.xml -X mission-cancer.xlsx
```
- **exporter-negotiator-orphans.py** - finds collections with Negotiator representatives and auto-population candidates.  
```
python3 exporter-negotiator-orphans.py negotiator_reps.xlsx -X negotiator_orphans.xlsx
```
- **exporter-obesity.py** - obesity collections (including pediatric segmentation) with sample totals.  
```
python3 exporter-obesity.py -X obesity.xlsx
```
- **exporter-pediatric.py** - pediatric and pediatric-only collections based on age ranges.  
```
python3 exporter-pediatric.py -X pediatric.xlsx
```
- **exporter-quality-label.py** - quality label export for biobanks/collections and combined labels.  
```
python3 exporter-quality-label.py
```

## Additional helper scripts

- **get-contacts.py** - contact generator for Negotiator invitation pipelines.  
```bash
./get-contacts.py --purge-all-caches -X contacts.xlsx
```
- **COVID19DataPortal_XMLFromBBMRIDirectory.py** - builds COVID-19 Data Portal XML from Directory collections.  
```bash
python3 COVID19DataPortal_XMLFromBBMRIDirectory.py -x bbmriDirectory_Covid19DataPortal.xml
```
- **add_orphacodes.py** - adds OrphaCodes to a Directory EMX export.  
```bash
python3 add_orphacodes.py -d directory.xlsx -O en_product1.xml -o directory-with-orpha.xlsx
```
- **directory-stats.py** - per-biobank statistics for collections, samples, donors, services, collection types, service types, and fact-sheet consistency. Sample and donor totals combine explicit countable values with order-of-magnitude fallback estimates for top-level collections only, so subcollections do not double-count parent holdings. Fact-sheet warnings report missing/invalid all-star rows and mismatches against collection-level totals. Withdrawn biobanks and collections are excluded by default; use `-w/--include-withdrawn` to include them, or `--only-withdrawn` to report only withdrawn content. You can filter by biobank `country` (`-c/--country`), by staging area code parsed from the biobank ID (`-A/--staging-area`, for example `EXT`), and by collection type (`-t/--collection-type`). Filter values accept comma-delimited OR semantics within each filter, while different filters are combined as AND. Biobank rows are listed in lexicographic ID order, except pure `EXT` views, which are sorted by country first and then by ID to make non-member output easier to scan.  
```bash
python3 directory-stats.py -N

python3 directory-stats.py -X directory-stats.xlsx -N

python3 directory-stats.py -c DE -A EXT -N

python3 directory-stats.py -c DE,FR -A EXT -t CASE_CONTROL,POPULATION -N

python3 directory-stats.py --only-withdrawn -N
```
- **AI review workflow** - use the Codex skill `run-ai-checks` explicitly when you need full AI-model review of live Directory data. That workflow refreshes `ai-check-cache/` only for genuinely AI-only findings; deterministic regex/heuristic text checks already run in the normal QC pipeline via `TextConsistency`. Current AI-reviewed domains include access-governance metadata gaps, participant clinical-profile gaps, data-category gaps, and material-metadata gaps. After refreshing AI-reviewed findings, use `python3 data-check.py -N -r` to validate that the full QC path stays free of stale-cache warnings, and use `python3 data-check.py -r | rg 'AI:Curated'` to inspect the emitted cache-backed warnings themselves.  
- **geocoding_2022.py** - generates geoJSON output from Directory data and config.  
```bash
python3 geocoding_2022.py geocoding.config -o bbmri-directory-geojson
```
- **install_certifi.py** - refreshes root certificates for Directory access.  
```bash
python3 install_certifi.py
```

## Directory tables modifier (use with caution!)

`directory-tables-modifier.py` modifies staging tables. This is a sensitive component: always verify schema, input files, and intended records before applying changes.

Key safety points:
- Requires `.env` with `DIRECTORYTARGET`, `DIRECTORYUSERNAME`, `DIRECTORYPASSWORD` (or pass CLI overrides).
- Schema is required (`-s/--schema`) and corresponds to the staging area name shown in the Molgenis Navigator (for example `BBMRI-EU`).
- Use a node staging area for normal edits. `ERIC` is the aggregated public schema and should normally not be edited with this tool.
- If you explicitly request `-s ERIC`, the script requires an extra interactive approval unless `-f/--force` is used.
- Table name is required for import, delete, export, and sync (`-T/--table`).
- Actions are mutually exclusive: import (`-i`), delete (`-x`), export (`-e`), sync (`-y`).
- Deletions always require interactive confirmation unless `-f/--force` is used.
- Use `-n/--dry-run` to preview changes without modifying data.
- `-v/--verbose` shows record-level details; `-d/--debug` adds connection/auth details.
- Exit codes: `0` success, `2` input error, `3` aborted, `1` runtime error.

### Import records
- Use `-i/--import-data` with `-T/--table`.
- Format auto-detects by extension; override with `-F/--file-format csv|tsv` if the filename is wrong or missing an extension.
- Use `-S/--separator` to override the field separator for CSV/TSV import/delete/export/sync (for example `';'` or `\\t`).
- Use `-N/--national-node` to populate a missing `national_node` column for all imported rows (warns if the column already exists).
- Use `-R/--id-regex` and/or `-C/--collection-id` to import only matching rows (defaults to `id`/`collection` columns; override with `--id-column`/`--collection-column`).
- For `-T CollectionFacts`, use `-k/--k-donors <k>` and/or `-K/--k-samples <k>` to enforce k-anonymity during import/sync: rows below threshold are skipped and counted in statistics.
- If Molgenis rejects an import due to a missing `national_node` and `-N` is not set, the script falls back to `-s/--schema` as the `national_node` and warns.

Federated login note:
- If you use federated login (LifeScience Login/AAI) in the Directory UI, set a local password for API use: Directory web interface → Sign in → Account (top right) → Update password.

Examples:
```bash
python3 directory-tables-modifier.py -s BBMRI-EU -T Biobanks -i Biobanks.csv

python3 directory-tables-modifier.py -s BBMRI-EU -T Collections -i Collections.data -F csv -n -v

python3 directory-tables-modifier.py -s BBMRI-EU -T Biobanks -i Biobanks.tsv -N BBMRI-EU

python3 directory-tables-modifier.py -s BBMRI-EU -T Biobanks -i Biobanks.csv -S ';'

python3 directory-tables-modifier.py -s BBMRI-EU -T Collections -i Collections.tsv -R '^COLL_' -C BB_001

python3 directory-tables-modifier.py -s BBMRI-EU -T CollectionFacts -i facts.tsv -k 10 -K 10
```

### Delete records (table contents only)
- Provide `-x/--delete-data` with `-T/--table`.
- Deletes only matching records, not the whole table.
- Requires interactive confirmation unless `-f/--force` is set.
- To delete by filters only (no file), use `-x --delete-filter-only` together with `-R` and/or `-C`.
- Use `--export-on-delete <file>` to back up the rows that will be deleted.

Examples:
```bash
python3 directory-tables-modifier.py -s ERIC -T Collections -x delete.tsv

python3 directory-tables-modifier.py -s ERIC -T Collections -x delete.tsv -f

python3 directory-tables-modifier.py -s ERIC -T CollectionFacts -x --delete-filter-only -R '^FACT_' -C BB_001

python3 directory-tables-modifier.py -s ERIC -T Collections -x delete.tsv --export-on-delete delete-backup.tsv
```

### Export records
- Export table data to CSV/TSV without modifying: `-e/--export-data`.
- Filter by ID regex (`-R/--id-regex`) and/or collection IDs (`-C/--collection-id`).

Examples:
```bash
python3 directory-tables-modifier.py -s ERIC -T CollectionFacts -e facts.tsv

python3 directory-tables-modifier.py -s ERIC -T CollectionFacts -e facts.csv -R '^FACT_' -C BB_001 -C BB_002
```

### Sync table contents
- Sync mode (`-y/--sync-data`) makes table contents match exactly the input file by:
  1) for full-table sync (no `-R/-C`): truncating current table contents, then importing file contents;
  2) for filtered sync (`-R` and/or `-C`): deleting only matching server rows, then importing only matching file rows.
- The server operation is still non-atomic, but the script now creates a temporary pre-sync backup of the full matching server rows (all columns, including technical columns) and attempts rollback automatically if import fails.
- Use `-n/--dry-run` first and strongly consider `--export-on-delete` as a backup.
- In filtered sync mode, any file rows that do **not** match `-R/-C` are ignored and reported as warnings.

Examples:
```bash
python3 directory-tables-modifier.py -s BBMRI-EU -T CollectionFacts -y facts-sync.tsv -n -v

python3 directory-tables-modifier.py -s BBMRI-EU -T CollectionFacts -y facts-sync.tsv --export-on-delete facts-pre-sync-backup.tsv

python3 directory-tables-modifier.py -s BBMRI-EU -T CollectionFacts -y facts-sync.tsv -R '^fact:' -C bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE
```

### TSV parsing overrides
If TSV files use non-standard quoting/escaping, adjust with:
- `--tsvQuoteChar`, `--tsvEscapeChar`, `--tsvQuoting`, `--tsvNoDoublequote`.
- `-S/--separator` can override CSV/TSV delimiters (for example `;` or `\\t`).

### Working examples (sanitized)
The following are adapted from real runs. Collection IDs are masked consistently as `bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE`.

Dry-run delete of facts for one collection (no file, filter-only): 
previews the exact rows that would be deleted, without changing data. Uses `-C` to target a single collection and `-n` to ensure no writes.\
```bash
./directory-tables-modifier.py -s BBMRI-EU -v -T CollectionFacts -N BBMRI-EU -x --delete-filter-only -C bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE -n
```

Delete facts for one collection (no file, filter-only): 
removes only the matching fact rows; confirmation is required unless `-f` is used.\
```bash
./directory-tables-modifier.py -s BBMRI-EU -v -T CollectionFacts -N BBMRI-EU -x --delete-filter-only -C bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE
```

Import facts with forced approval: 
imports all rows in `facts.tsv` into `CollectionFacts` without interactive prompts (`-f`).\
```bash
./directory-tables-modifier.py -s BBMRI-EU -i facts.tsv -v -T CollectionFacts -N BBMRI-EU -f
```

Export facts for comparison: 
exports the current `CollectionFacts` table to a TSV for review or diffing.\
```bash
./directory-tables-modifier.py -s BBMRI-EU -e facts-cmp.tsv -v -T CollectionFacts -N BBMRI-EU
```

Export filtered facts for one collection: 
exports only rows for the specified collection to inspect changes in isolation.\
```bash
./directory-tables-modifier.py -s BBMRI-EU -e facts-cmp.tsv -v -T CollectionFacts -N BBMRI-EU -C bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE
```

Dry-run delete using a file plus a collection filter: 
previews deleting only the filtered rows listed in `facts-cmp.tsv`.\
```bash
./directory-tables-modifier.py -s BBMRI-EU -v -T CollectionFacts -N BBMRI-EU -x facts-cmp.tsv -C bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE -n
```
 
Delete using a file plus a collection filter:
deletes only matching rows from the file and collection filter; confirmation is required.\
```bash
./directory-tables-modifier.py -s BBMRI-EU -v -T CollectionFacts -N BBMRI-EU -x facts-cmp.tsv -C bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE
```

## Collection descriptor updater

`collection-factsheet-descriptor-updater.py` analyzes one collection in the `ERIC` schema of the configured Directory target, derives collection-level descriptors from the fact sheet, and can update the `Collections` table in the explicit target staging area.

Key behavior:
- analysis always reads facts from `ERIC` in the configured Directory target
- updates are written only to the explicitly provided `-s/--schema`
- the tool checks whether the collection ID staging prefix matches the requested schema (for example `EU` -> `BBMRI-EU`) and asks for confirmation on mismatch unless `-f/--force` is used
- the target collection must exist in the requested schema or the tool fails with an error
- by default the tool only appends missing descriptor values; use `--replace-existing` to allow removing/replacing existing multi-value descriptors
- numbers of samples and donors are updated from the all-star fact row when that row is present, even without `--replace-existing`
- `NAV` fact-sheet material does not propagate to collection metadata when other material types are present; `*` fact-sheet aggregates are ignored for descriptor derivation
- ICD-10 hierarchy is respected when appending diagnoses: broader existing codes such as `urn:miriam:icd:C18` are retained and cover specific fact-sheet codes such as `urn:miriam:icd:C18.0`
- age updates cover the full fact-sheet span from minimum to maximum age represented by the fact rows; holes between fact-sheet age buckets are ignored because collection metadata can advertise only one continuous range

Examples:
```bash
python3 collection-factsheet-descriptor-updater.py -c bbmri-eric:ID:EU_BBMRI-ERIC:collection:CRC-Cohort -s BBMRI-EU -n -v

python3 collection-factsheet-descriptor-updater.py -c bbmri-eric:ID:CZ_FOO:collection:BAR -s BBMRI-CZ

python3 collection-factsheet-descriptor-updater.py -c bbmri-eric:ID:CZ_FOO:collection:BAR -s BBMRI-CZ --replace-existing -f
```

## QC update workflow

`data-check.py` can export a structured update plan from warnings that carry machine-readable fixes via `-U/--export-update-plan`, and `qcheck-updater.py` can list, dry-run, review, and apply those fixes to a staging-area schema.

Examples:
```bash
python3 data-check.py -U qc-updates.json -r -N

python3 qcheck-updater.py -i qc-updates.json -s BBMRI-CZ --list

python3 qcheck-updater.py -i qc-updates.json -s BBMRI-CZ -n --module AP

python3 qcheck-updater.py -i qc-updates.json -s BBMRI-CZ --module AP --force
```

Key behavior:
- workflow:
  - run `data-check.py -U ...` on `ERIC`
  - inspect the generated plan with `qcheck-updater.py --list`
  - dry-run the selected subset with `-n/--dry-run`; it uses the same interactive per-update review flow as a real apply, but stops before writing data
  - apply the reviewed subset interactively or with `-f/--force`
- `--list` is the non-destructive human-readable inspection mode; it shows the same normalized multi-value field presentation as interactive review
- the exported JSON plan contains per-update and whole-file checksums; the updater warns when the file or individual updates were edited after export, but the user can still proceed deliberately
- each update carries the expected current field value seen at export time; if the live staging-area value changed before apply, the updater warns and requires explicit confirmation unless `-f/--force` is used
- in interactive mode, live-value mismatches are reviewed per update; declining one mismatched update skips only that update instead of aborting the whole run
- unordered multi-value fields such as `data_use`, `type`, `diagnosis_available`, `materials`, and `sex` are compared canonically, so pure field reordering does not create false mismatches during review/apply
- filtering is supported by exact entity ID, hierarchy root ID (biobank or collection), staging area, originating check ID, update ID, module, and confidence
- hierarchy selection:
  - `--entity-id` selects one exact target entity
  - `--root-id` expands over a biobank -> collection/subcollection hierarchy or a collection -> subcollection hierarchy
  - contacts are intentionally not treated as hierarchy roots because they are shared across unrelated entities
- `uncertain` updates stay in the plan so the user can review alternative resolutions, but they should only be applied deliberately after narrowing the selection
- module filters use the same visible QC check-prefix family that users see in warning IDs:
  - `AP` for DUO/access-policy fixes from `AccessPolicies`
  - `CC` for collection-content/type fixes from `CollectionContent`
  - `C19` for COVID-specific fixes from `COVID`
  - `FT` for fact-sheet-derived diagnosis/material/sex/age/count fixes from `FactTables`
  - `TXT` for deterministic narrative-to-structure fixes from `TextConsistency`
- semantic detail still lives in `update_id`, for example `access.duo.disease_specific_research` or `diagnoses.add.covid_acute_u07_1`
- current implementation of `qcheck-updater.py` applies collection-level updates only
- ontology-backed fixes carry human-readable explanations in the update plan so the reviewer can see what a term such as `DUO:...` means before approving the change
- DUO identifiers are normalized internally, so `DUO_0000007` and `DUO:0000007` are treated as the same term during checks and update application
- append-mode review shows both the final target value and the incremental value being added, to avoid giving the impression that a multi-value field would be replaced
- fact-derived and QC-derived rationales stay field-specific; age-range caveats are shown only on age updates, not on diagnoses, materials, or counts
- this workflow is only appropriate when the BBMRI Node maintains metadata directly in the Directory staging area; if the staging area is synchronized or imported from another authoritative source, fix the primary source instead of applying updates here
