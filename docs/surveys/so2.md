# SO2 Survey Workflows

Run examples from the repository root. See [UpSet rendering](upsets.md) for the canonical R workflow.

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

Association heatmaps use the checked-in `survey-mappings/so2_2025_association_heatmaps.json` registry. With `describe`, they use paired merged observations under the response-identity protocol below; unresolved submissions remain separate, and conflicting single-choice answers do not enter complete-case pairs. Their denominator is not necessarily a count of unique institutions and does not establish causality. Existing row-based JSON retains its original row interpretation when rerendered. All axes show answer labels directly, not numeric keys. Long answers use reviewed display labels and wrapped question titles (up to three curated lines); e.g. the personnel/infrastructure panel shows `Need more info`, `Yes`, and `No`. Full answers, category order and statistics remain in JSON; shortening is presentation-only. Rerun `describe` to embed current reviewed display metadata in the payload. Contact and free-text fields, including `q_111`, are excluded. `--include-exploratory-association-heatmaps` enables only explicitly marked exploratory panels. Do not publish small-cell panels until a complementary-suppression policy is approved.

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

`describe` merges repeated submissions with a shared explicit biobank ID or
reviewed offline mapping, never by similar institution names alone. The default
mapping is `survey-mappings/so2_2025_response_identities.json`; select another with
`--response-identities FILE`. This source-specific file is local and ignored by
Git. Fresh clones fall back to the committed, empty
`so2_2025_response_identities.example.json`; create a reviewed local mapping to
restore source-specific grouping/country corrections. Explicit missing paths
fail rather than falling back. Reviewed row mappings apply only to the stated XLSX
hash. Unresolved submissions remain separate observations, so the resulting count
is not necessarily an established count of unique biobanks.

Agreeing answers count once; blanks are filled from other submissions. Conflicting
single-choice answers appear as **Conflicting answers**, multi-choice selections
are combined with differences flagged, and distinct free text is retained. The
JSON preserves every original submission and identity/country decision under
`responses_summary`. The unnumbered **Responses Summary**, after Abbreviations,
lists received/merged counts and duplicate institutions by country/source rows.
Charts, heatmaps and UpSets consistently use these merged observations.
Standalone UpSets no longer include deviation plots; the terminology-experience
UpSet (`q_018`, Section 11.1 in this export) is wider and rotated for readability.
Regenerate the R bundle and run R again after changing response merging, then
pass that folder to `describe --upset-assets-dir ...`.
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
Legal barriers (`q_063`-`q_066`), organisational barriers (`q_068`-`q_071`) and
collaboration ratings (`q_073`-`q_076`) also receive two joint-response profile
figures within their matrix sections: the 12 most frequent combinations and a
compact complete chart fitted to one page. Columns preserve the four subquestions;
colours denote answer categories and adjacent bars show exact profile frequencies.
Each figure states its coverage and uses all included observations as its percentage
denominator. Missing, conflicting and not-applicable states remain separate, never
converted into negative responses or numeric scores. Original donuts remain.
With `--output-chart-dir`, the six vector PDFs use `profiles-<group>-top12.pdf`
and `profiles-<group>-complete.pdf`. Joint combinations and source-row membership
are recorded in the sensitive JSON `response_profiles` field; no institution names
appear in the figures. These are observed-pattern summaries, not association tests.
The complete figure may require zooming for dense profiles. MuCP is unaffected.

The final **QM vs traceability readiness** section scores the seven verified
SO2 fields `q_053`, `q_055`–`q_058`, `q_060`, and `q_061`. No additional option
is needed when running the full SO2 schema. It explains the formulas and exact
choice-to-score rules from `survey-mappings/so2_2025_readiness_scores.json` and
provides one deduplicated vector heatmap plus a country-grouped, multipage institution score
table. These are exploratory self-reported scores, not quality certifications.

The main heatmap counts agreeing score vectors once per reviewed observation.
Conflicting vectors remain separate alternatives in the table and are excluded
from that heatmap; missing/unrecognised answers are unscorable, never zero.
The report states complete-pair, conflict and incomplete-observation counts.
Reference replay is enabled only when the ignored local policy
`survey-mappings/so2_2025_readiness_reference.json` exists and its reviewed input
hash matches the workbook. That private policy contains the reference matrix,
source-row binding and documented blank override; none is distributed in Git.
This legacy source-submission audit remains in JSON only: neither it nor the
source-reference figure is rendered in the report or exported as a chart.
The deduplicated view never receives a reference-only override.
Custody selections use the documented first-match precedence; differing selected
scores are flagged. QMS manual-digital/paper values remain literal 0.66/0.33.

`--output-chart-dir` adds only `readiness-main.pdf` through
the normal chart publication pipeline. The JSON stores the versioned rules, their
semantic SHA-256, original answers, scores, alternatives, diagnostics and both
matrices under `readiness_scores`. `render-descriptive-report` validates and
recomputes that saved model without opening the private reference workbook or archive. Scoring
models are cross-checked against the report's preserved raw responses, observation
membership and workbook/form hashes; those evidence fields cannot be removed to
bypass validation or set to null. Scoring field UIDs, types and all choices are validated against
the actual form manifest, not just against schema declarations. Conflicting
alternatives stay together on a table page.
Legacy payloads without the model remain renderable but do not gain this section until
`describe` is rerun. These changes do not affect MuCP reports.

Raw SO2 XLSX/XML exports and EUS archives, private scoring archives, workbooks, reference
vectors and replay policy, local identity decisions, source-specific MuCP quantity reviews, and
generated reports are excluded from Git. The generated SO2 form manifest,
question/scoring definitions and invented test fixtures are shared. Obtain
response exports and optional raw form/reference files separately; do not add
them to commits. The complete reference-vector replay is an optional local
test when both the ignored reference vectors and replay policy exist. Portable numerical,
missingness, conflict, provenance and layout tests use invented responses.

Standalone SO2 single-choice charts are donuts, retaining the same counts,
percentages and including/excluding-missing variants. Bars are ordered by decreasing
count (ties retain source order), including ordinal and missing categories; the
underlying JSON values remain unchanged. Interoperability UpSet `q_018` is rotated
on its own page; observed-minus-expected plots are not included. These presentation
rules do not change MuCP/combined reports. Existing UpSet bundles still retain their
deviation assets for validation compatibility.
The published TeX is self-contained and can be compiled without a fragments
directory. PDF rendering invokes `xelatex` twice directly so the table of contents is resolved; a missing compiler fails PDF
or standalone-chart rendering rather than producing a partial PDF. With
`--output-chart-dir`, the directory must be new or empty by default and receives standalone
vector-PDF charts generated from the same PGF/TikZ source as the report. Each chart includes its question, denominator, unit, and missingness context, while the
JSON payload records its report-relative path. The report includes full source provenance, a post-contents abbreviation glossary, and per-question `N`, `A`, `M`, and applicability information. Bar percentages use `oAR` (answering rows) or `oIR` (included rows); empty
free-text questions explicitly state `No text responses.` File outputs are new by default and all output paths must be distinct from inputs and from one another. `describe --overwrite` deliberately replaces its JSON, TeX, PDF, and chart-directory outputs after successful regeneration; it never permits an output to alias an input.
Publication uses target-directory sibling stages and rolls back the invocation on
write, compile, or publication failure.
