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

## Directory And MIABIS Comparison

`directory-miabis-conformance.py` is a separate implementation check, not a QC
plugin. It reads schema metadata and DataCategories/ServiceTypes references,
never entity records. All supported terms are compared with pinned official
MIABIS sources. Reviewed counterparts/extensions remain visible; unresolved
meanings require review. Relevant Directory GitHub history includes intermediate
changes and file renames, not just first/last versions.

The checker parses the linked Collection and Services component attributes as
well as the controlled lists. Disagreements between reference documents are
reported separately from Directory differences. Source formats it cannot assess
produce an incomplete audit, not a claim of compliance. Development-status
overviews are context, not proof that a component is a published release.
Observed contents are matched against historical source intervals; identical
contents at several revisions remain multiple candidates. No-match results list
added/missing terms and changed definitions/properties. None of these matches
establishes which commit was deployed or its deployment date.

```bash
python3 directory-miabis-conformance.py -v --refresh \
  --output-json directory-miabis.json \
  --output-markdown directory-miabis.md
python3 directory-miabis-conformance.py --offline \
  --output-markdown directory-miabis-offline.md
```

Without output options Markdown goes to stdout. `--output-tex differences.tex`
creates a fragment for review, not an automatic Manual publication. Existing
reports require `--overwrite`; failed publication restores earlier contents.

Defaults: production/ERIC; MIABIS commit
`272d05e792e312f1fe56e24eac37d43ce9376bf1`; Directory history endpoint
`0aac60c44c68ff1733c3d10f3669ec9967951872`, baseline
`843af5c2af4ee681e700f2a149213199b40919df` (before network inheritance removal).
`--miabis-revision`, `--directory-revision`, `--history-start-revision` accept full
immutable SHAs, not branches. A changed reference does not approve new semantic
bindings. `--guidance` selects reviewed JSON advice.

Use `--directory-url URL`, `-P/--schema`, and shared `-u/-p/-t` authentication
for other targets/private schemas. `DIRECTORYTARGET` supplies the URL default.
`--cache-dir` selects the upstream-source cache. Metadata has its own target/
schema-keyed cache under `DIRECTORY_CACHE_ROOT` or the working directory.
`--offline` forbids all checker requests and requires cached inputs. `--refresh`
refreshes Directory metadata with visible cached fallback. Source failures must
not be interpreted as empty vocabularies or successful comparisons.

Exit codes: `0` complete without unreviewed differences; `1` complete requiring
review; `2` invalid/unavailable/incomplete inputs; `3` interrupted. Scope is the
two vocabularies and relevant references, not the full MIABIS model. Results do
not emit entity warnings or update plans. Tool operation and implementation
comparison findings belong in this documentation; the Data Manager's Manual
focuses on changes that affect data entry and migration. Further check proposals are recorded in
[the consistency assessment](vocabulary-consistency-assessment.md).

At the reviewed reference revisions, MIABIS lists 14 dataset types and 32 service
types. Directory adds terms such as Biological samples and Transcriptomic
Dataset; an extension alone is not a defect. Other sample-derived dataset is
narrower than MIABIS Other. Service comparisons such as Genomics resource versus
Genomics service still require definition-level review. MIABIS Collection lists
cardinality 1 for Dataset type, whereas Directory allows multiple categories;
the intended interpretation needs confirmation by the specification and
implementation maintainers. This is not advice to remove supported categories.
The linked allowed-value lists agree with the consolidated lists at the pinned
revision. The reference README marks aggregate components as under development;
a commit labelled "v4" alone does not establish a published normative release.

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
