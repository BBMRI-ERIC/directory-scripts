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

Association heatmaps use the checked-in `survey-mappings/so2_2025_association_heatmaps.json` registry. They describe paired submitted response rows only; their denominator is not a count of unique institutions and does not establish causality. Exact `No`/`Yes` axes use direct answer labels and wrapped question titles; longer answer sets use numeric keys with a bounded legend. Contact and free-text fields, including `q_111`, are excluded. `--include-exploratory-association-heatmaps` enables only explicitly marked exploratory panels. Do not publish small-cell panels until a complementary-suppression policy is approved.

`survey-so2-directory.py describe` and `render-descriptive-report` are a
standalone, Directory-free workflow. They do not load Directory data, request
credentials, resolve institutions, or create update proposals. `export-eus-form-json`
regenerates the reviewable form manifest from the committed EUS archive; `describe`
reads that manifest, the versioned survey schema, and workbook, while
`render-descriptive-report` renders an existing descriptive-statistics JSON payload
without reopening source files.

```bash
python3 survey-so2-directory.py export-eus-form-json \
  --form-eus survey-mappings/SO2_2025-u65uym7bs7d8bfs7j7hpcwoc1y.eus \
  -o survey-mappings/so2_2025_form.json

python3 survey-so2-directory.py describe \
  -i Content_Export_SO2_2025_20260313.xlsx \
  --descriptive-schema survey-mappings/so2_2025_descriptive_report.json \
  --form-json survey-mappings/so2_2025_form.json \
  -o so2-descriptive.json \
  --output-tex so2-descriptive.tex \
  --output-pdf so2-descriptive.pdf \
  --output-chart-dir so2-descriptive-charts

# Deliberately replace all prior describe artifacts at these paths
python3 survey-so2-directory.py describe \
  -i Content_Export_SO2_2025_20260313.xlsx \
  --descriptive-schema survey-mappings/so2_2025_descriptive_report.json \
  --form-json survey-mappings/so2_2025_form.json \
  -o so2-descriptive.json \
  --output-tex so2-descriptive.tex \
  --output-pdf so2-descriptive.pdf \
  --output-chart-dir so2-descriptive-charts \
  --overwrite

python3 survey-so2-directory.py render-descriptive-report \
  -i so2-descriptive.json \
  --output-pdf so2-descriptive-rerendered.pdf
```

The observation unit is every nonblank submitted worksheet row. Counts are
unweighted and are not deduplicated to institutions, biobanks, or countries.
`describe` requires the generated JSON form manifest so payloads and reports use
its actual single-choice, multiple-choice, free-text, matrix, and requiredness
metadata. Only explicit manifest regeneration decodes EUS Java serialization;
ordinary reporting does not require that decoder. Single-choice matrix controls
are rendered as a parent section with one pie-chart subsection per matrix row;
the parent reports the matrix response type and mandatory/optional status once.
Use `--max-piechart-ratio WIDTH:HEIGHT` with either descriptive command to set
the maximum pie-chart width:height ratio. It defaults to `4:3`; `16:9` permits
wider charts and `1:2` permits taller charts. If full labels cannot fit within
the selected proportion, the pie uses numbered labels with a full legend below.
Structured-response contribution tables are omitted from the normal report; pass `--long-report` to either descriptive command to include grouped `Value | Country | Institutions` tables. Free-text response tables remain in both report forms. Explicit empty free-text placeholders are omitted, and HTTP(S) URLs are rendered as short hyperlinks. Contribution evidence retains the reported country, institution, and free-text answers; source-row provenance remains in the JSON payload rather than the readable tables. Free-text tables use ISO alpha-2 country codes and omit parent context by default. Pass `--include-parent-context` to show a `Parent context` column containing complete raw parent responses; it intentionally does not show the schema's semantically filtered subset, which would be incomplete context. The JSON retains both raw and semantic parent evidence, and a missing semantic trigger is diagnosed without omitting the text. Repeated normalized country/institution combinations are flagged as suspected repeated responses but are never removed. Treat generated
JSON, TeX, PDFs, and chart directories as sensitive because they can contain
institution names and free text.

TeX-only output requires no compiler and does not render standalone chart PDFs.
The published TeX is self-contained and can be compiled without a fragments
directory. PDF rendering invokes `xelatex` twice directly so the table of contents is resolved; a missing compiler fails PDF
or standalone-chart rendering rather than producing a partial PDF. With
`--output-chart-dir`, the directory must be new or empty by default and receives standalone
vector-PDF charts generated from the same PGF/TikZ source as the report. Each chart includes its question, denominator, unit, and missingness context, while the
JSON payload records its report-relative path. The report includes full source provenance, a post-contents abbreviation glossary, and per-question `N`, `A`, `M`, and applicability information. Bar percentages use `oAR` (answering rows) or `oIR` (included rows); empty
free-text questions explicitly state `No text responses.` File outputs are new by default and all output paths must be distinct from inputs and from one another. `describe --overwrite` deliberately replaces its JSON, TeX, PDF, and chart-directory outputs after successful regeneration; it never permits an output to alias an input.
Publication uses target-directory sibling stages and rolls back the invocation on
write, compile, or publication failure.

### Optional ComplexUpset figures

The descriptive report can embed the approved eight multi-choice UpSet and
observed-minus-expected deviation figures without making R a Termux runtime
dependency. First generate the JSON payload, then create the external bundle:

```bash
python3 survey-so2-directory.py export-descriptive-upset-r \
  -i so2-descriptive.json --output-dir so2-upsets
```

Run `so2-upsets/render-descriptive-upsets.R` in an R environment containing
`ComplexUpset`, `ggplot2`, and `jsonlite`. See
[SO2 Descriptive UpSet Assets](so2-descriptive-upsets.md) for native-R and
Termux Debian-proot installation and execution commands. Finally rerun the
normal `describe` command with `--upset-assets-dir so2-upsets`. An explicitly
empty existing assets directory
adds omission notes; a nonempty directory must contain a current completed
bundle whose canonical hash matches the newly generated payload. The final PDF
embeds the figures, while TeX references the sidecar PDFs and therefore needs
the validated bundle retained for later recompilation.

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
