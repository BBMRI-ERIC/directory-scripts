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

## Installation
- Verify installation:  
  ``
python3 -m ensurepip
``
- For each of the above packages `pip3  install --upgrade <package>`
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
- Requires `.env` with `TARGET`, `USERNAME`, `PASSWORD`.
- Default schema is `ERIC` (override with `-s/--schema`).
- Deletions always require interactive confirmation unless `-f/--force` is used.
- Use `-n/--dry-run` to preview changes without modifying data.
- `-v/--verbose` shows record-level details; `-d/--debug` adds connection/auth details.
- Exit codes: `0` success, `2` input error, `3` aborted, `1` runtime error.

### Import records
- Use `-i/--import-data` with `-T/--import-table` (recommended).
- Format auto-detects by extension; override with `-I/--import-format csv|tsv` if the filename is wrong or missing an extension.
- Use `-N/--national-node` to populate a missing `national_node` column for all imported rows (warns if the column already exists).

Examples:
``
python3 directory-tables-modifier.py -i Biobanks.csv -T Biobanks
``
``
python3 directory-tables-modifier.py -i Collections.data -T Collections -I csv -n -v
``
``
python3 directory-tables-modifier.py -i Biobanks.tsv -T Biobanks -N BBMRI-EU
``

### Delete records (table contents only)
- Provide `-x/--delete-data` with `-t/--delete-table`.
- Deletes only matching records, not the whole table.
- Requires interactive confirmation unless `-f/--force` is set.

Examples:
``
python3 directory-tables-modifier.py -x delete.tsv -t Collections
``
``
python3 directory-tables-modifier.py -x delete.tsv -t Collections -f
``

### Facts export and deletion
- Export facts to CSV/TSV without modifying: `-e/--export-facts`.
- Filter by fact ID regex (`-R/--fact-id-regex`) and/or collection IDs (`-C/--collection-id`).
- Delete facts with `-F/--delete-facts` plus the same filters (confirmation required).

Examples:
``
python3 directory-tables-modifier.py -e facts.tsv
``
``
python3 directory-tables-modifier.py -e facts.csv -R '^FACT_' -C BB_001 -C BB_002
``
``
python3 directory-tables-modifier.py -F -R '^FACT_' -C BB_001 -f
``

### TSV parsing overrides
If TSV files use non-standard quoting/escaping, adjust with:
- `--tsvQuoteChar`, `--tsvEscapeChar`, `--tsvQuoting`, `--tsvNoDoublequote`.
