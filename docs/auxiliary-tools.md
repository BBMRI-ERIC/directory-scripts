# Auxiliary tools

These commands support analysis, search, conversions, and one-off workflows but
are not part of the main exporter family.

## EOSC organisation matching

`eosc-organisation-matcher.py` matches active Directory juridical persons to an
EOSC-A membership XLSX and prepares incremental Codex research packets. Existing
decisions and reviewed negative comparisons are reused rather than researched
again. See the [EOSC matcher guide](eosc-organisation-matcher.md) for exports,
registry migration, focused AI packets, partial imports and explicit approval.

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

## SO2 descriptive statistics

`survey-so2-directory.py describe` and `render-descriptive-report` are a
standalone, Directory-free workflow. They do not load Directory data, request
credentials, resolve institutions, or create update proposals. `describe` reads
the versioned survey schema and workbook, while `render-descriptive-report`
renders an existing descriptive-statistics JSON payload without reopening the
workbook.

```bash
python3 survey-so2-directory.py describe \
  -i Content_Export_SO2_2025_20260313.xlsx \
  --descriptive-schema survey-mappings/so2_2025_descriptive_report.json \
  -o so2-descriptive.json \
  --output-tex so2-descriptive.tex \
  --output-pdf so2-descriptive.pdf \
  --output-chart-dir so2-descriptive-charts

python3 survey-so2-directory.py render-descriptive-report \
  -i so2-descriptive.json \
  --output-pdf so2-descriptive-rerendered.pdf
```

The observation unit is every nonblank submitted worksheet row. Counts are
unweighted and are not deduplicated to institutions, biobanks, or countries.
Contribution tables retain the reported country, institution, source row, and
free-text answers; repeated normalized country/institution combinations are
flagged as suspected repeated responses but are never removed. Treat generated
JSON, TeX, PDFs, and chart directories as sensitive because they can contain
institution names and free text.

TeX-only output requires no compiler and does not render standalone chart PDFs.
The published TeX is self-contained and can be compiled without a fragments
directory. PDF rendering invokes `xelatex` directly; a missing compiler fails PDF
or standalone-chart rendering rather than producing a partial PDF. With
`--output-chart-dir`, the directory must be new or empty and receives standalone
vector-PDF charts generated from the same PGF/TikZ source as the report. Each
chart includes its question, denominator, unit, and missingness context, while the
JSON payload records its report-relative path. The report includes full source
provenance and per-question `N`, `A`, `M`, and applicability information; empty
free-text questions explicitly state `No text responses.` File outputs must be
new, and all output paths must be distinct from inputs and from one another.
Publication uses target-directory sibling stages and rolls back the invocation on
write, compile, or publication failure.

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
