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
