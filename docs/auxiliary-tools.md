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

## Combined SO2 and Multi-Country Project evidence

`survey-so2-directory.py merge-mucp` is a separate command, not a mode of
`describe`. It groups source responses by canonical Directory biobank ID,
selects the requested cohort (by default all MuCP responses), and preserves
every contributing response and collection scope. Resolved responses use a
**unique selected biobank**; unresolved responses remain separate, explicitly
labelled source reporting units, and national summaries retain national scope.
Survey-specific denominators include only selected participants of that survey.

Start with JSON and a matching-review packet, without compiling figures:

```bash
python3 survey-so2-directory.py merge-mucp \
  -i Content_Export_SO2_2025_20260916.xlsx \
  --descriptive-schema survey-mappings/so2_2025_descriptive_report.json \
  --form-json survey-mappings/so2_2025_form.json \
  --mucp-json survey_results.json \
  --mucp-schema survey_results.schema.json \
  -o so2-mucp-combined.json \
  --output-match-review so2-mucp-match-review.md
```

The command requires `jsonschema` in addition to existing repository dependencies
(`python3 -m pip install -r requirements.txt`). R and Java are not required.
Directory cache/authentication/schema options follow the other read tools:
active entities are included by default, `-w` includes withdrawn biobanks, and
`--only-withdrawn` restricts the cohort. Match uniqueness is checked against all
loaded contact owners before applying that scope.

For a combined report, add `--output-tex so2-mucp-combined.tex` and
`--output-pdf so2-mucp-combined.pdf`. Optional
`--output-biobank-pdf-dir so2-mucp-biobanks` produces individual dossiers;
`--output-chart-dir so2-mucp-charts` produces presentation-ready vector charts.
These options can require substantial compilation time. Existing targets are
protected by default; `--overwrite` replaces them only after successful staging.
All output paths must be distinct from inputs and from each other, including
nested directories and symlink aliases. A requested PDF failure does not publish
a partial JSON/report set.

### Matching and reviewed overrides

Matching prioritizes explicit IDs (collection parents come from Directory),
unique full contact emails, then unique exact institution/country identities.
Shared emails, fuzzy names, conflicting identity evidence and national summaries
are not automatically assigned to biobanks. The review packet is suitable for
manual or Codex-assisted investigation; it does not itself accept candidates.

Use `--match-overrides PATH` for a private copy of
`survey-mappings/so2_mucp_biobank_overrides.json`. A decision contains `survey`,
`source_record_id`, `identity_fingerprint`, `action` (`accept` or `reject`),
`biobank_id` for acceptance, `reason`, `reviewer`, and `reviewed_on`. Copy the
source fingerprint from the generated review packet. Changes to that record's
identity require re-review; an unrelated newly appended response does not
invalidate unchanged decisions. Do not commit private institutional decisions
without an explicit data-sharing review.

`--so2-findings PATH` can reuse reviewed SO2-to-Directory identities. Older
findings only recorded a workbook filename, which is not a safe content binding.
The command reports the exact hashes needed; after reviewing the correspondence,
add a binding to `input_bindings` in your overrides file:

```json
{
  "so2_sha256": "SHA256_OF_THE_EXACT_WORKBOOK",
  "findings_sha256": "SHA256_OF_THE_EXACT_FINDINGS",
  "reviewer": "reviewer identifier",
  "reason": "Verified row identities against this exact export"
}
```

This is one array item, not a replacement for the override-file envelope.
Changed/reordered workbook rows or an unbound legacy findings file fail clearly.
Approximate/ambiguous findings still require individual reviewed decisions.
The old `resolved_by_institution_name_certain` status can include aliases, so
it also requires a record-level override; a workbook hash does not prove an
identity match. Frozen exact matches still undergo contradiction checks.

For a national summary, a reviewed decision may assign a specific collection
scope using `scope_id`; neither the entire record nor its submission scope may
be accepted as one biobank. Unassigned material remains in the diagnostics and
the all-MuCP source view, without repeating the assigned collection's evidence.
Internal projected record IDs retain the original response ID as provenance;
the source input is never changed. Outputs cannot overwrite implicitly loaded
registries or other configurations, even with `--overwrite`.
Quantity index entries follow uniquely owned source references; entries whose
scope cannot be proved remain diagnostic-only rather than being copied into
each biobank's quantity inventory.

### Interpreting the combined report

The merge-only option `--table-biobank-repeated-entries {empty,dtto}` controls
repeated biobank cells in combined-report tables; the default `empty` leaves
repeats blank and `dtto` prints an italic ditto marker. It applies only where
rows have a canonical biobank column, including scoped quantities,
clinical/interoperability evidence, quantity contributions and their selection status, source
quantity support, and free-text answer tables. It does not group institution
lists, generic value/country summaries, individual dossiers, or standalone
`describe`/`render-descriptive-report` output.

Biobank blocks are ordered by country, display name, then canonical Directory ID;
equal names never merge identities. Section 2.2 has one logical table with country
banners and continuation notes identifying the previous page's last country/biobank.
Unknown countries come last; bank boundaries use only midrules. Other long tables use independent longtable blocks
with a fixed, wrapped “Continued: biobank name” header for that block. This avoids
mutable TeX header state and keeps continuation pages identifiable. Small blocks
do not repeat generic column headings; each block ends with a booktabs midrule.

- Each answer is labelled **SO2** or **MuCP**, with original row/response ID,
  question, scope and evidence references retained in JSON. Thematic groups show
  individual contributions, not an unexplained merged boolean. Their JSON
  `contribution_ids` point to the separate source-qualified evidence items.
- The report is MuCP-led: cohort/sample-size profile, MuCP Part B/Part C
  statistics (including MuCP-only questions), complementary SO2 enrichment and
  remaining SO2 statistics. Biobank dossiers and matching details appear at the
  back when `--include-dossiers` is requested; matching details are always included.
  Crosswalks do not restrict question coverage.
- Section 1's matching inventory is also stored additively as `matching_breakdown`
  in the combined JSON; existing `matching_summary` fields remain unchanged. SO2
  and MuCP totals count source response rows once by source-record ID and stored
  resolution status, not independent MuCP questionnaires or total respondent
  biobanks. Accepted institutions outside the overlap remain accepted. Distinct
  accepted Directory IDs determine per-survey counts; the analytical cohort is
  the chosen join, and unresolved identities may hide additional overlap.
  Institution-name groups and unresolved-repeat counts are display-only and do not
  establish unique banks. Country-summary records are separate non-biobank evidence;
  missing/unknown countries appear under `Unknown`. Contacts remain masked unless
  the existing contact-details opt-in is enabled.
- Donors, individuals and research participants share the analytical unit
  `donors`; the literal source unit remains in JSON. Samples and aliquots remain
  separate. Size bands include only one eligible unqualified scoped count per
  biobank and use eligible scoped counts as their percentage denominator.
  Concise biobank counts distinguish counts for identifiable collections or the
  whole biobank, counts mentioned in answers, and no reported counts; missing evidence
  is not a zero count. Qualified, multi-scope and unclear-unit evidence remains
  distinguishable from genuinely absent quantity evidence.
- The clinical/phenotypic view pairs MuCP affirmative scoped evidence with SO2
  staff terminology/standards experience. It does not establish interoperability
  implementation or that the answers concern the same collection.
- Dossiers begin with MuCP response IDs and source filenames. They show readable
  `[SO2]`/`[MuCP]` questions, one Yes/No/qualified answer per source contribution,
  meaningful collection scope and substantive qualifications. Empty qualifiers
  are omitted. `--extended-evidence` additionally shows technical question IDs,
  source-record references, locators and evidence identifiers. JSON provenance
  remains complete regardless of this presentation option.
- Combined PDF compilation repeats XeLaTeX until table-of-contents references
  stabilize (minimum two passes, bounded additional passes); unstable or failed
  compilation does not publish a partial report. The shared PDF preamble requires
  Libertine and Inconsolata's bundled OpenType fonts, with monospaced text scaled
  to 0.85; these are TeX dependencies, not Python packages.
- Agreeing repeat submissions count once per biobank; conflicting answers remain
  explicit categories. Different collection scopes remain separate evidence.
- MuCP selected/true is Yes and explicit false is No. A present applicable
  unticked checkbox is also a derived No, while its raw null and unmarked state
  stay intact in JSON. Missing option keys, not-asked, ambiguous and conditional
  answers are not No. Differing unlinked submissions have uncertain scope, not
  an automatically established collection contradiction. A positive collection answer is described
  as reported in at least one scope, never uniformly true of every collection.
- Qualifications, narratives, source warnings and non-additive count descriptions
  are retained. Neither collections nor Part B/Part C counts are blindly summed.
- Long dossier/text responses use continuation rows. Large locator lists are
  summarized with their count in PDFs, with the complete references retained in JSON.
- MuCP group bars have per-option unknown/partial, qualified-positive and
  varying-positive diagnostics in JSON. Combined PDFs omit the overlapping
  scope-state coverage tables in default, long and extended modes.
- If the source supplies no document-level evidence for an answer, JSON retains
  an exact pointer and hash of the input JSON answer, explicitly marked as lacking
  document evidence; this does not invent a page or spreadsheet locator.
- MuCP N/A/M means selected MuCP participants / informative derived answer states /
  genuinely missing or indeterminate states. Present applicable unticked options
  contribute No rather than M. SO2 conflicts and scope variation are separate
  categories, so its N need not equal A plus M. Percentages distinguish the
  known-answer denominator from the full cohort.
- Percentages state their bases. Sparse exploratory heatmaps/UpSets are omitted
  with a reason; this is not a privacy/anonymization guarantee.
- The material/data-type quantity table reports eligible collection-size totals only for
  collections explicitly linked to each type. It keeps whole-biobank
  fallbacks and actual type-specific measurements in separate source rows, reports
  contributor biobank/scope counts, and shows `Not reported` rather than zero
  when no eligible amount exists. Excluded-unit, qualification and other
  uncertainty counts remain traceable in the stored JSON aggregates and are
  summarized in the table. The same reported people may occur in more than one
  collection or type: type totals are not unique-person estimates and
  must not be added across types. A collection may contribute to multiple
  type rows without increasing an all-collection country total more than
  once.
- Quantity charts use linear stacked bars, with colored confirmed contributions
  and distinct gray shades for uncertain reported counts, including bounds,
  approximations and conflicting or potentially overlapping populations. A
  inclusive bar label is `confirmed: X, total: Y`; **total is a display sum, not
  a verified population total**. Country counts always have two charts per unit:
  confirmed only, then confirmed plus uncertain, with the same country rows.
  Zero in the confirmed-only chart means no confirmed contribution, not absence
  of samples or donors. Material/data-type charts also label both amounts.
  The supporting table separates confirmed and uncertain numbers. Legends preserve qualifiers
  such as `>`, `>=` and approximation. Proven duplicate measurements appear once.
  All material types share a chart per compatible unit and measurement
  meaning, with country segments. Actual type-specific quantities remain separate
  from collection-size context. Unknown-unit numbers have separate panels; ages,
  dates and incidental numeric text are retained for interpretation, never guessed
  into count widths. A compact source-coverage table includes records without
  reported counts: missing is not zero. Type membership is source-proven, not
  inferred from another collection. Donor counts across collections or types are
  not estimates of unique people and must not be added across types. Countries
  are alphabetical from the top, with a wrapped contribution legend. Countries are the Directory
  biobank's reported country, not donor residence or cohort origin. `describe`
  and its charts are unchanged; the former quantity-coverage matrices remain
  omitted from the combined report.
- Reporting country codes use `TR` for Turkey and `MNE` for Montenegro without
  changing identity mappings or original answers. Current/cumulative reporting
  periods remain visible in source descriptions and evidence tables; they no
  longer create separate date-specific country graphs.
- The combined report puts charts and short overview tables first: cohort,
  MuCP profile, Part B, Part C, grouped criteria, cross-survey enrichment, SO2.
  **Detailed evidence** follows those sections and retains quantity context,
  selection/exclusion explanations, source coverage, clinical/interoperability
  evidence, response/free-text/qualification tables and UpSet membership tables.
  Earlier sections link directly to the relevant evidence; chart legends remain
  beside charts. Matching/source review is Appendix A, and optional dossiers are
  Appendix B (`--include-dossiers`). Standalone `describe` placement is unchanged.
  Biobank-name links to dossiers appear only when that appendix is included.
- Quantity support tables show which country/material/data-type view included each source
  count, or why it was excluded/covered. Temporal bases stay visible in totals
  and support rows. Collection count evidence is included in reporting inventories
  without claiming a whole-biobank size. Long chart legends paginate with context;
  labels for small totals remain readable inside the plot.
- Combined heatmaps use curated short headings and direct tick labels; both full
  source questions appear below each heading. Their presentation does not
  change category meanings or the standalone `describe` heatmaps. Exported
  combined heatmap chart PDFs carry the same title and full questions.

Dedicated professional contact fields and recognizable emails are hidden in
PDFs by default; `--include-contact-details` deliberately enables them.
Arbitrary narratives can contain names or other identifying information that
cannot be automatically anonymized reliably. JSON, review packets, TeX, PDFs
and charts must therefore be treated as sensitive and reviewed before sharing.

### Optional combined ComplexUpset figures

#### Cohort selection and compact output

`merge-mucp --join {inner,all-MuCP,all-SO2,outer}` selects the report cohort:
`inner` means verified identities in both surveys, `all-MuCP` (default) includes every MuCP response,
`all-SO2` means every resolved SO2 biobank, and `outer` means either survey.
Unresolved/review/excluded MuCP responses are retained in `all-MuCP` and `outer`,
with their original matching decisions. Unresolved sources have local `mucp-source:`
identifiers, not invented Directory IDs. They remain separate reporting units;
national summaries retain national scope. The overview reports exact source coverage
and explains that reporting-unit counts are not a verified count of distinct biobanks.
The report states how many selected biobanks supplied no response to each survey.
They are not counted as unanswered questions or negative answers. Survey-specific
percentages use selected participants in that survey; shared analyses use participants
in both required surveys before applying question-level completeness rules.

The main PDF omits biobank dossiers by default. Add `--include-dossiers` for that
appendix; `--output-biobank-pdf-dir` independently requests individual dossier PDFs.
Complete answer-level provenance remains in JSON either way.

Section 2.2 groups counts by country name with gray country banners and identifies
the collection beside every statement when known. Section 2.3 is table-only.
Section 2.4 consolidates countries into one bar each, stacked by contributing
biobanks; donor/sample/aliquot graphs are separate, with linear axes only.
Country labels use Directory metadata for resolved biobanks and the survey country
for unresolved reporting units, not the participants' country of residence.
Material types appear together in linear graphs stacked by country. Data types
are shown separately. Actual type-specific counts are not added to overall counts
of collections reporting that type.
Different type totals may count the same people and must not be added together.

Source-reviewed quantity interpretations are applied only to their exact input JSON
hash, original response hash and source-file checksums. Original answer evidence is
unchanged. The size table suppresses source-owned duplicate numeric-index mentions;
unresolved units and collection overlap remain explicitly qualified.
The size table prints a numeric source sentence once, rather than repeating every
extracted number beside it; all extracted values and source references remain in
JSON. Complete count fields accept grouped thousands (`16.000`), `mio`/`million`,
approximation (`~`) and open-ended trailing `+` bounds. Person-unit synonyms are
accepted for the B/C individual-count questions, not for mismatched table headers.
Section 2.4 also shows separate **non-additive reported counts** where quantities
cannot safely enter exact stacks. Their points retain bounds/approximations and
Part B/C context; they are not country totals. This includes Danish counts whose
population relationships are unresolved. A response supplying no numeric count
cannot contribute a size point, even though it remains included in the report.
In Section 2.3, "Different reported counts; cannot safely add them" means no single
additive total can be established. It does not necessarily mean erroneous answers:
counts may concern different populations or reference times. Consult their source
context in Section 2.2; the original reason code remains available in JSON.

MuCP question charts retain the full participating population only, without the
extra answered-only companion. Standalone `describe` is unchanged.

Every shared UpSet bar is labelled `I1`, `I2`, etc. Its immediately following table
lists the exact intersection's biobanks grouped by country. Bar heights are exclusive
intersection counts, not left-hand set totals. Bundle validation checks actual built
bar/matrix order and counts, including ties and empty patterns. New cohort or renderer
changes invalidate old bundles; regenerate both R and PDFs, never edit hashes.

For the current local workflow use `--join all-MuCP`, generate the new bundle with
`--output-upset-r-dir so2-mucp-all-MuCP-upsets`, run its generated R script, and rerun
the identical inputs with `--upset-assets-dir so2-mucp-all-MuCP-upsets --overwrite`.
Do not supply old overlap-only assets. Final outputs can continue to use
`so2-mucp-readable.json`, `.tex` and `.pdf`.

Default definitions include MuCP biospecimens, OMICs and available data, SO2
technology access, and two source-labelled cross-survey intersections pairing
MuCP OMICs or clinical/imaging data with SO2 technology access. These show
co-reported evidence at the biobank level, not that a technology generates the
reported data or that the same collection has both. Regenerate existing bundles
after changing these definitions or the reviewed overlap cohort.
The required SO2 `Other` and `I don't know` checkboxes are not concrete technology
access sets; their original answers remain in the descriptive statistics and
evidence dossiers. These figures cover the named technologies, not an inferred
availability of unspecified technologies.
Unknown technology answers and Other-only selections are excluded from these
matrices with a recorded reason, not converted into all-zero technology vectors.

Add `--output-upset-r-dir so2-mucp-upsets` to the initial merge command. Run:

```bash
Rscript so2-mucp-upsets/render-descriptive-upsets.R
```

Then rerun the same `merge-mucp` inputs with
`--upset-assets-dir so2-mucp-upsets --overwrite` and the desired PDF targets;
omit `--output-upset-r-dir` on that rerun. The folder is read-only input during
embedding. Empty/missing optional figures are clearly marked omitted; a supplied
nonempty stale or incomplete bundle blocks publication. For Termux, use the
Debian proot installation/bind workflow documented in the SO2 UpSet section below.
The validator checks the actual CSV vectors, renderer script and PDF hashes;
regenerate the bundle after analytical or renderer changes rather than editing
its integrity markers manually.

The default classified MuCP UpSet includes answered all-unticked groups as
all-zero rows. An absent dot means No reported in the represented applicable
scopes, not universal biological absence. Unknown, conditional, conflicting and
incomplete-scope patterns are excluded with reasons; cross-survey SO2 unknowns
remain unknown. Distinct collection reports may refer to different collections.
The external bundle still generates both UpSet and exploratory deviation PDFs,
but the combined report embeds only UpSets by default. Pass
`--include-upset-deviations` to include the exploratory independence-model
pages; they are not significance tests. Refresh the R bundle after changes to
source data, policy, cohort or curated presentation rather than editing hashes.

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
provides two vector heatmaps plus a country-grouped, multipage institution score
table. These are exploratory self-reported scores, not quality certifications.

The main heatmap counts agreeing score vectors once per reviewed observation.
Conflicting vectors remain separate alternatives in the table and are excluded
from that heatmap; missing/unrecognised answers are unscorable, never zero.
The report states complete-pair, conflict and incomplete-observation counts.
Reference replay is enabled only when the ignored local policy
`survey-mappings/so2_2025_readiness_reference.json` exists and its reviewed input
hash matches the workbook. That private policy contains the reference matrix,
source-row binding and documented blank override; none is distributed in Git.
Without it, the second heatmap is an unadjusted source-submission view. The main
deduplicated view never receives a reference-only override.
Custody selections use the documented first-match precedence; differing selected
scores are flagged. QMS manual-digital/paper values remain literal 0.66/0.33.

`--output-chart-dir` adds `readiness-main.pdf` and `readiness-source.pdf` through
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
