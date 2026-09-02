# Auxiliary tools

These commands support analysis, search, conversions, and one-off workflows but
are not part of the main exporter family.

## Directory statistics

`directory-stats.py` reports per-biobank collection, sample, donor, service,
collection-type, service-type, and fact-sheet consistency statistics. Explicit
counts and order-of-magnitude fallbacks use top-level collections to avoid
double-counting subcollections.

```bash
python3 directory-stats.py -N
python3 directory-stats.py -X directory-stats.xlsx -N
python3 directory-stats.py -c DE,FR -A EXT -T CASE_CONTROL,POPULATION -N
python3 directory-stats.py --only-withdrawn -N
```

Country (`-c`), staging area (`-A`), and collection type (`-T`) accept
comma-separated OR values; different filters combine with AND.

## Full-text search

`full-text-search.py` builds a schema- and withdrawal-scope-specific Whoosh
index and accepts Lucene query syntax.

```bash
./full-text-search.py 'bbmri-eric:ID:UK_GBR-1-101'
./full-text-search.py '"Cell therapy"~3'
./full-text-search.py '*420*'
./full-text-search.py --purge-cache directory --purge-cache index -v 'DE_*'
./full-text-search.py --only-withdrawn 'withdrawn biobank'
```

## SO2 survey analysis

`survey-so2-directory.py` compares the SO2 Datafication survey export with
Directory data using editable mappings. It can generate machine-readable
findings, a TeX/PDF report, qcheck-compatible update proposals, and an R script
plus CSV for modality UpSet, deviation, and respondent matrix figures.

```bash
python3 survey-so2-directory.py analyze \
  -i Content_Export_SO2_2025.xlsx \
  -m survey-mappings/so2_2025_directory_mapping.json \
  --objectives-mapping-file \
    survey-mappings/so2_2025_question_to_strategic_objectives.json \
  -o so2-findings.json \
  --output-tech-upset-prefix so2-modalities

python3 survey-so2-directory.py render-report \
  -i so2-findings.json --output-pdf so2-report.pdf

python3 survey-so2-directory.py export-update-plan \
  -i so2-findings.json -o so2-updates.json \
  --min-confidence almost_certain
```

The survey workflow analyzes respondents only; it does not interpret every
Directory biobank missing from the survey as a finding. Review and edit mapping
JSON rather than hard-coding uncertain respondent matches.

## Other utilities

| Script | Purpose | Example |
|---|---|---|
| `get-contacts.py` | Generate contacts for Negotiator invitation workflows | `./get-contacts.py --purge-all-caches -X contacts.xlsx` |
| `COVID19DataPortal_XMLFromBBMRIDirectory.py` | Generate COVID-19 Data Portal XML | `python3 COVID19DataPortal_XMLFromBBMRIDirectory.py -x covid.xml` |
| `add_orphacodes.py` | Add ORPHA codes to an offline Directory EMX workbook | `python3 add_orphacodes.py -d directory.xlsx -O en_product1.xml -o with-orpha.xlsx` |
| `install_certifi.py` | Refresh certificate configuration for Directory HTTPS access | `python3 install_certifi.py` |

`add_orphacodes.py` remains useful for workbook conversion. For live Directory
quality work, prefer the conservative ORPHA/ICD checks and fix proposals in
`data-check.py` followed by `qcheck-updater.py`.
