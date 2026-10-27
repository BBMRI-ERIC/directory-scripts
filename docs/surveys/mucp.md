# Combined MuCP And SO2 Workflows

Run examples from the repository root. See [UpSet rendering](upsets.md#combined-report-assets) for external charts.

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

For an updated MuCP archive, extract its JSON and schema into a private local
directory and pass those paths to `--mucp-json` and `--mucp-schema`. The parser
retains submission labels, source-page ranges and source links from incremental
exports. Keep the reviewed matching overrides, but do not reuse old UpSet PDFs:
regenerate the bundle for the new input. Quantity-review catalogues are bound
to exact input and evidence hashes; never change those hashes without verifying
the corresponding responses and source evidence remain equivalent.
Qualified/ambiguous checkbox marks remain ambiguous rather than being counted
as an explicit Yes or No.

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
