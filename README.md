# BBMRI-ERIC Directory Validation Scripts
## Requirements
- Python >= 3.6
- The following python packages:
  - networkx
  - geopy
  - validate_email
  - xlsxwriter
  - py3dns (on Windows this silently conflicts if dnspython is already installed)
  - requests
  - diskcache
  - yapsy (see below if you run Python 3.12 or higher)
  - whoosh
  - roman
  - typing-extensions
  - openpyxl
  - pytest (for unit tests)

## Installation
- Verify installation:  
  ``
python3 -m ensurepip
``
- For each of the above packages `pip3  install --upgrade <package>`
- For test dependencies only: `pip3 install -r requirements-test.txt`
- Ensure that file `/etc/resolve.conf` exists. If it does not exist create it with the following contents:  
  ``
nameserver 8.8.8.8
``
- Download the MOLGENIS Python API library:  
  ``
pip3 install molgenis-emx2-pyclient dotenv molgenis-emx2-directory-client
``\
If you run into GraphQL errors when retrieving data from the Directory, upgrade the client with:\
  ``
  pip3 install --upgrade molgenis-emx2-pyclient
  ``
- Install/update root certificates (also check install_certifi.py script)  
  ``
pip3 install --upgrade certifi
``
- If you want support for checking mappings of ORPHA codes to ICD-10 codes for RD biobanks, you need to get en_product1.xml from
  http://www.orphadata.org/cgi-bin/ORPHAnomenclature.html

- If you have Python 3.12 or higher, for the time being (December, 2024) you need a patched version of yapsy module to deal with instability in the Python - some stable components being removed from the Python core. Here is a quick howto:
     ``
     git clone https://github.com/AmeyaVS/yapsy.git
     cd yapsy/package
     python -m build
     pip install --force-reinstall dist/Yapsy-2.0.0-py3-none-any.whl
``

## Data quality checks

The simplest way to run the default validation suite is:  
``
python3 data-check.py
``

Purge all caches (directory + remote checks) and output both stdout and XLSX:  
``
python3 data-check.py --purge-all-caches -X test_results.xlsx
``

Purge only the directory cache and output to XLSX only, with verbose logging:  
``
python3 data-check.py -v --purge-cache directory -N -X test_results.xlsx
``

Enable ORPHA-to-ICD checks (requires en_product1.xml):  
``
python3 data-check.py -O en_product1.xml
``

Debug mode with fresh caches:  
``
python3 data-check.py -d --purge-all-caches
``

## Unit tests

Run all unit tests (pytest):
``
pytest -q
``

Run focused tests for reusable directory helpers:
``
pytest -q tests/test_directory.py
``

Run live cache-mode tests against Directory (fresh fetch + cached snapshot):
``
pytest -q tests/test_directory_live_cache_modes.py --live-directory --live-directory-mode both
``

Run only cached-mode live tests:
``
pytest -q tests/test_directory_live_cache_modes.py --live-directory --live-directory-mode cached
``

Run only fresh-mode live tests:
``
pytest -q tests/test_directory_live_cache_modes.py --live-directory --live-directory-mode fresh
``

Optional live-test settings:
- `--live-directory-schema <SCHEMA>` (or env `DIRECTORY_TEST_SCHEMA`) selects schema/staging area (default: `ERIC`).
- Env `DIRECTORYUSERNAME` and `DIRECTORYPASSWORD` can be set for authenticated live runs; if unset, tests run without login.

By default, live tests are skipped unless `--live-directory` is provided. They run in an isolated temporary working directory so cache purge checks do not wipe your regular local cache.

## Searching in the Directory

- **full-text-search.py** - full text search of the Directory using Whoosh with [Lucene search syntax](https://lucene.apache.org/core/2_9_4/queryparsersyntax.html).
  - `./full-text-search.py 'bbmri-eric:ID:UK_GBR-1-101'`
  - `./full-text-search.py '"Cell therapy"~3'` (note shell escaping of quotes)
  - `./full-text-search.py '*420*'`
  - `./full-text-search.py --purge-cache directory --purge-cache index -v 'DE_*'`
  - `./full-text-search.py 'myID' | perl -ne "while(<>) {if(m/^.*?'id':\\s+'(.+?)'.*$/) {print \\$1 . \"\\n\";}}"`

## Exporters

- **exporter-all.py** - exports all biobanks/collections with aggregate counts and optional filters; can output withdrawn entities.  
``
python3 exporter-all.py -X all.xlsx
``
- **exporter-bbmri-cohorts.py** - BBMRI Cohorts network statistics plus warnings/errors aggregation.  
``
python3 exporter-bbmri-cohorts.py -X bbmri_cohorts_stats.xlsx -XWE bbmri_cohorts_warnings.xlsx
``
- **exporter-cohorts.py** - lists COHORT/POPULATION_BASED collections and summaries per country/biobank.  
``
python3 exporter-cohorts.py -X cohorts.xlsx
``
- **exporter-country.py** - counts biobanks/collections per country (stdout or XLSX).  
``
python3 exporter-country.py
``
- **exporter-covid.py** - COVID-related collections/biobanks with sample/donor totals.  
``
python3 exporter-covid.py -X covid.xlsx
``
- **exporter-diagnosis.py** - diagnosis inspection utility (development-focused logging).  
``
python3 exporter-diagnosis.py -d > diagnosis-exporter.log 2>&1
``
- **exporter-ecraid.py** - ECRAID-relevant collections (BSL2/3 and pathogen material) and institutions.  
``
python3 exporter-ecraid.py -X ecraid.xlsx
``
- **exporter-institutions.py** - lists juridical persons (institutions) per country.  
``
python3 exporter-institutions.py -X institutions.xlsx
``
- **exporter-mission-cancer.py** - cancer and pediatric-cancer analytics using ICD/ORPHA mapping.  
``
python3 exporter-mission-cancer.py -O en_product1.xml -X mission-cancer.xlsx
``
- **exporter-negotiator-orphans.py** - finds collections with Negotiator representatives and auto-population candidates.  
``
python3 exporter-negotiator-orphans.py negotiator_reps.xlsx -X negotiator_orphans.xlsx
``
- **exporter-obesity.py** - obesity collections (including pediatric segmentation) with sample totals.  
``
python3 exporter-obesity.py -X obesity.xlsx
``
- **exporter-pediatric.py** - pediatric and pediatric-only collections based on age ranges.  
``
python3 exporter-pediatric.py -X pediatric.xlsx
``
- **exporter-quality-label.py** - quality label export for biobanks/collections and combined labels.  
``
python3 exporter-quality-label.py
``

## Additional helper scripts

- **get-contacts.py** - contact generator for Negotiator invitation pipelines.  
``
./get-contacts.py --purge-all-caches -X contacts.xlsx
``
- **COVID19DataPortal_XMLFromBBMRIDirectory.py** - builds COVID-19 Data Portal XML from Directory collections.  
``
python3 COVID19DataPortal_XMLFromBBMRIDirectory.py -x bbmriDirectory_Covid19DataPortal.xml
``
- **add_orphacodes.py** - adds OrphaCodes to a Directory EMX export.  
``
python3 add_orphacodes.py -d directory.xlsx -O en_product1.xml -o directory-with-orpha.xlsx
``
- **directory-stats.py** - legacy biobank size estimation stats.  
``
python3 directory-stats.py -N
``
- **geocoding_2022.py** - generates geoJSON output from Directory data and config.  
``
python3 geocoding_2022.py geocoding.config -o bbmri-directory-geojson
``
- **install_certifi.py** - refreshes root certificates for Directory access.  
``
python3 install_certifi.py
``

## Directory tables modifier (use with caution!)

`directory-tables-modifier.py` modifies staging tables. This is a sensitive component: always verify schema, input files, and intended records before applying changes.

Key safety points:
- Requires `.env` with `DIRECTORYTARGET`, `DIRECTORYUSERNAME`, `DIRECTORYPASSWORD` (or pass CLI overrides).
- Schema is required (`-s/--schema`) and corresponds to the staging area name shown in the Molgenis Navigator (for example `BBMRI-EU`).
- Table name is required for import, delete, and export (`-T/--table`).
- Actions are mutually exclusive: import (`-i`), delete (`-x`), export (`-e`).
- Deletions always require interactive confirmation unless `-f/--force` is used.
- Use `-n/--dry-run` to preview changes without modifying data.
- `-v/--verbose` shows record-level details; `-d/--debug` adds connection/auth details.
- Exit codes: `0` success, `2` input error, `3` aborted, `1` runtime error.

### Import records
- Use `-i/--import-data` with `-T/--table`.
- Format auto-detects by extension; override with `-F/--file-format csv|tsv` if the filename is wrong or missing an extension.
- Use `-N/--national-node` to populate a missing `national_node` column for all imported rows (warns if the column already exists).
- Use `-R/--id-regex` and/or `-C/--collection-id` to import only matching rows (defaults to `id`/`collection` columns; override with `--id-column`/`--collection-column`).
- If Molgenis rejects an import due to a missing `national_node` and `-N` is not set, the script falls back to `-s/--schema` as the `national_node` and warns.

Federated login note:
- If you use federated login (LifeScience Login/AAI) in the Directory UI, set a local password for API use: Directory web interface → Sign in → Account (top right) → Update password.

Examples:
``
python3 directory-tables-modifier.py -s ERIC -T Biobanks -i Biobanks.csv
``
``
python3 directory-tables-modifier.py -s ERIC -T Collections -i Collections.data -F csv -n -v
``
``
python3 directory-tables-modifier.py -s ERIC -T Biobanks -i Biobanks.tsv -N BBMRI-EU
``
``
python3 directory-tables-modifier.py -s ERIC -T Collections -i Collections.tsv -R '^COLL_' -C BB_001
``

### Delete records (table contents only)
- Provide `-x/--delete-data` with `-T/--table`.
- Deletes only matching records, not the whole table.
- Requires interactive confirmation unless `-f/--force` is set.
- To delete by filters only (no file), use `-x --delete-filter-only` together with `-R` and/or `-C`.
- Use `--export-on-delete <file>` to back up the rows that will be deleted.

Examples:
``
python3 directory-tables-modifier.py -s ERIC -T Collections -x delete.tsv
``
``
python3 directory-tables-modifier.py -s ERIC -T Collections -x delete.tsv -f
``
``
python3 directory-tables-modifier.py -s ERIC -T CollectionFacts -x --delete-filter-only -R '^FACT_' -C BB_001
``
``
python3 directory-tables-modifier.py -s ERIC -T Collections -x delete.tsv --export-on-delete delete-backup.tsv
``

### Export records
- Export table data to CSV/TSV without modifying: `-e/--export-data`.
- Filter by ID regex (`-R/--id-regex`) and/or collection IDs (`-C/--collection-id`).

Examples:
``
python3 directory-tables-modifier.py -s ERIC -T CollectionFacts -e facts.tsv
``
``
python3 directory-tables-modifier.py -s ERIC -T CollectionFacts -e facts.csv -R '^FACT_' -C BB_001 -C BB_002
``

### TSV parsing overrides
If TSV files use non-standard quoting/escaping, adjust with:
- `--tsvQuoteChar`, `--tsvEscapeChar`, `--tsvQuoting`, `--tsvNoDoublequote`.

### Working examples (sanitized)
The following are adapted from real runs. Collection IDs are masked consistently as `bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE`.

Dry-run delete of facts for one collection (no file, filter-only): 
previews the exact rows that would be deleted, without changing data. Uses `-C` to target a single collection and `-n` to ensure no writes.\
``
./directory-tables-modifier.py -s BBMRI-EU -v -T CollectionFacts -N BBMRI-EU -x --delete-filter-only -C bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE -n
``

Delete facts for one collection (no file, filter-only): 
removes only the matching fact rows; confirmation is required unless `-f` is used.\
``
./directory-tables-modifier.py -s BBMRI-EU -v -T CollectionFacts -N BBMRI-EU -x --delete-filter-only -C bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE
``

Import facts with forced approval: 
imports all rows in `facts.tsv` into `CollectionFacts` without interactive prompts (`-f`).\
``
./directory-tables-modifier.py -s BBMRI-EU -i facts.tsv -v -T CollectionFacts -N BBMRI-EU -f
``

Export facts for comparison: 
exports the current `CollectionFacts` table to a TSV for review or diffing.\
``
./directory-tables-modifier.py -s BBMRI-EU -e facts-cmp.tsv -v -T CollectionFacts -N BBMRI-EU
``

Export filtered facts for one collection: 
exports only rows for the specified collection to inspect changes in isolation.\
``
./directory-tables-modifier.py -s BBMRI-EU -e facts-cmp.tsv -v -T CollectionFacts -N BBMRI-EU -C bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE
``

Dry-run delete using a file plus a collection filter: 
previews deleting only the filtered rows listed in `facts-cmp.tsv`.\
``
./directory-tables-modifier.py -s BBMRI-EU -v -T CollectionFacts -N BBMRI-EU -x facts-cmp.tsv -C bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE -n
``
 
Delete using a file plus a collection filter:
deletes only matching rows from the file and collection filter; confirmation is required.\
``
./directory-tables-modifier.py -s BBMRI-EU -v -T CollectionFacts -N BBMRI-EU -x facts-cmp.tsv -C bbmri-eric:ID:EU_BBMRI-ERIC:collection:COLL_EXAMPLE
``
