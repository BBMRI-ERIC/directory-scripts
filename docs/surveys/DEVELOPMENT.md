# Survey Functionality Specifications

These contracts supplement [shared architecture](../../DEVELOPMENT.md).
Operator workflows live in [SO2](so2.md), [MuCP](mucp.md) and [UpSet](upsets.md).
Shared cache and quality contracts remain in [Directory cache scope](../../DEVELOPMENT.md#directory-cache-scope).

### SO2 survey analysis tool

- `survey-so2-directory.py` is a one-off survey-analysis CLI that still follows the repository's shared infrastructure rules:
- Technology-modality UpSet exports treat the required `Other` survey checkbox as non-positive unless `Technologies` free text says something concrete; the current graph uses direct-field NGS/proteomics/metabolomics, dedicated radiology/pathology questions, a separate `Genotyping / panels` bucket inferred from positive `Technologies` text, and `Other technology` only for the remaining positive `Technologies` details.
  - the generated R artifacts should include three coordinated outputs from the same CSV payload: the UpSet plot, the observed-minus-expected deviation plot, and a respondent-by-modality matrix plot
  - the matrix plot should label rows as `survey_row (CC): institution`, keep a white plot/panel background for export readability, and sort countries ascending with `A...` countries at the top of the plot
  - use `directory.py` for Directory access/cache/auth instead of ad hoc API calls
  - keep the survey-to-Directory mapping in editable JSON (`survey-mappings/so2_2025_directory_mapping.json`) so humans can correct Codex-produced assumptions
  - keep the survey-question to strategic-objective mapping in editable JSON (`survey-mappings/so2_2025_question_to_strategic_objectives.json`) so the report can aggregate findings by BBMRI SO2 objective without baking those assumptions into code
  - generate a machine-readable findings JSON first; treat TeX/PDF rendering as a second step that can render an edited findings JSON without re-reading the survey workbook
  - generate requested XeLaTeX PDF builds in a temporary working directory and write only the designated `.tex` / `.pdf` outputs into the repository or user-selected paths
  - invoke `xelatex` directly for PDF builds; do not route compilation through `latexmk -pdfxe`
- Resolution logic for survey respondents is intentionally conservative:
  - exact via biobank ID or collection ID when the survey provides them
  - certain via institution-name match when the normalized name, alias/acronym, or ID alias maps uniquely
  - approximate via institution-name similarity when there is no exact ID anchor; fuzzy matching should be accent-insensitive and robust to small typos
  - unresolved/missing when the respondent does not map cleanly into the Directory
- Do not invert the workflow by reporting every Directory biobank missing from the survey; only analyze survey respondents and their matched/missing Directory scope.
- WSI can currently only be analyzed through generic imaging signals (`type=IMAGE`, `data_categories=IMAGING_DATA`, imaging metadata, and free text). Do not invent a fake WSI-specific structured field until the Directory schema grows one.
- Survey-derived update plans may target both `BIOBANK` and `COLLECTION` entities; keep update generation conservative and avoid auto-writing free-text rewrites.
- Keep the findings JSON self-contained for later rendering: it should carry any derived strategic-objective tags needed for the PDF so `render-report` can work from the JSON alone.
- Keep repeated methodology text out of the main report body:
  - the main report should use short issue summaries plus compact concrete values for non-consistent findings
  - one canonical description per finding type belongs in the appendix, with clickable links from the summary/status tables
  - `Mapping` and `Entity` cells should remain breakable enough for PDF readability (`.` / `_` for mapping IDs; `-` / `:` / `_` / `.` for entity identifiers)

### Combined SO2 and MuCP biobank analysis

#### Cohort and compact-report contract (2026-10-05)

`merge-mucp --join {inner,all-MuCP,all-SO2,outer}` defaults to `all-MuCP`.
Version-2 outputs store `metadata.cohort` (mode, selected IDs, both surveys' accepted
reporting-unit IDs and actual verified intersection) and each bank's `survey_participation`. Both fields
are mandatory for v2; validation recomputes selection from the survey ID sets and
checks each participation flag against retained source records. Version-1
overlap payloads are legacy inner cohorts, never silently expanded. Matching
inventories retain all accepted/excluded/review source records regardless of join.
Survey-specific N counts selected participants in that survey; absent questionnaires
are separately counted, never reduced to No or unanswered question. Shared analyses
require every referenced survey before existing completeness/state policies.

`all-MuCP` and `outer` MUST retain every MuCP source response, including unresolved,
review and excluded identity decisions. Original decisions remain unchanged.
Unresolved sources receive local `mucp-source:` reporting identities with null
`directory_biobank_id`; this is not evidence that they are distinct biobanks.
National summaries retain their national scope and explicit reporting-unit kind.
Reviewed collection overrides create internal scope-projection records whose
scope/evidence ownership uses the virtual record ID; preserve original response
IDs separately for provenance. Remove assigned scopes, evidence and reviewed
quantities from the unassigned root projection to avoid double counting in
`all-MuCP`/`outer`. Never broadcast submission evidence to the assigned collection.
Project quantity indexes only through exact uniquely owned answer/count source
references. Foreign entries cannot enter another scope's numeric inventory;
unlocatable or ambiguous entries remain diagnostic-only in the root metadata.
A reviewed collection from a national response is a resolved biobank projection,
not itself a national summary; retain its original record type separately.
Protect implicit state, reporting-policy, presentation, quantity-review and
association registries and the combined output schema in output-collision
validation, including overwrite mode.
`metadata.mucp_source_coverage` records input/included counts and omitted source IDs.
The report must disclose these provisional units beside all cohort denominators.
The source-bound reviewed-quantity catalogue preserves original evidence and must
validate input, response and original-file hashes plus owned source scopes. Numeric
index mentions of the same owned source field/value must not duplicate reviewed counts.

Dossier appendix default is off; `--include-dossiers` enables it. Individual dossier
output is independent. Detailed quantity evidence uses gray centered country
headings, collection context in the answer column and only midrules between banks.
Country stacks pool compatible already-reconciled counts, keeping unlike units
and direct type measurements separate; a bank cannot contribute both collection
totals and whole-biobank fallback counts to the same compatible view. Material-type charts consolidate types with
country segments and linear-only axes; data-type graphs are distinct. All additive
stacks use linear raw count boundaries; logarithmic stacks are prohibited. The former
direct point chart is not part of combined composition. MuCP PartB/C retain only
full-participant pie variants; standalone describe remains unchanged.

Shared UpSet catalogues identify exclusive intersections by ordered bits, counts,
IDs and members. Combined version-2 R bundles record verified rendered bar/matrix
order and heights; validation rejects stale cohorts, swapped equal-height bars and
missing intersections. Reader membership tables are linked from figures into
Detailed evidence and name members by country. Unknown/absent questionnaires cannot become empty patterns. Source labels
remain verbatim; generated terminology uses material type/data type/technology.

The combined PDF is MuCP-led enrichment, not an SO2-led consistency report.
Order: overview, MuCP cohort profile, Part B, Part C, group statistics, cross-survey
enrichment/intersections, SO2 statistics, Detailed evidence, then Appendix A matching
review and optional Appendix B `--include-dossiers` biobank dossiers. Charts and
short summary tables precede all detailed response/quantity/qualification/member
tables. Stable hyperref targets connect summaries to deferred evidence. Chart
legends remain with their charts; source table relocation must not discard answers.
Biobank names link to dossiers only when that appendix is enabled; every internal
report hyperlink must resolve to a destination actually present in the document.
`render_statistics_sections` exposes opt-in `defer_evidence_tables` and returns
`evidence_fragments`; standalone describe defaults remain inline and unchanged.
Report-only country normalization uses TR/MNE and cannot change identity decisions,
fingerprints, original answers or source payloads. Country charts provide two
families per unit: confirmed-only and confirmed-plus-uncertain, with identical
country rows. Inclusive country/type labels are `confirmed: X, total: Y`; total
is explicitly a reported display sum, not a verified population count. Different
reporting dates no longer split panels, but remain attached to each contribution
and in confirmed as well as uncertain source descriptions. Part A submission
context belongs to Detailed evidence rather than an additional main survey part.
Temporal folding deduplicates identical source quantities across display classes
conservatively (uncertainty wins); partially shared aggregates or inconsistent
source ownership/values fail clearly rather than dropping or doubling counts.
Units and direct-type/collection-context meanings remain separate.
Zero in confirmed-only panels means no confirmed contribution, not a missing
source or proof that the population is zero. Compact
dossiers fold identical literal display values within each answer only, retain
source tags and scope, omit absent/blank qualifiers and widen the evidence field
column. `--extended-evidence` restores technical answer references; JSON evidence
must not change with this option. Privacy masking must not establish equality
between distinct source answers.
Dossiers share one appendix section and use numbered subsections, so cohorts
larger than 26 banks do not overflow LaTeX's A-Z appendix counter. Standalone
dossier PDFs retain their section heading.
Combined PDF compilation runs a minimum of two XeLaTeX passes and checks
auxiliary/TOC/bookmark bytes for convergence, allowing at most four additional
passes. Failure to converge blocks publication and cleans staging. Two passes
alone are insufficient when the generated TOC changes page count.

Section 1 includes the additive JSON field `matching_breakdown`; the legacy
`matching_summary` keys remain unchanged. The breakdown counts unique source
records by their stored resolution status (`accepted`, `unmatched`, `review`, or
`excluded`), deduplicating repeated representations only by survey and source-record
ID and rejecting contradictory decisions. Accepted biobank totals use distinct
Directory IDs, not institution-name groups. In particular, accepted records outside
the cross-survey intersection remain accepted even when stored in `unmatched_so2`
or `unmatched_mucp`. Country aliases use `survey_identity.country_key`; missing or
unknown values form an explicit `Unknown` group. Institution names are display
groups only and unresolved repeats are source-record multiplicities, not estimated
unique respondent banks. National/country-summary records are reported separately
as non-biobank evidence. The report describes the analytical cohort using its explicit
join and notes that unresolved identities may hide additional
overlap; source-record totals are not total respondent-biobank counts or independent
MuCP questionnaire counts. Contacts remain masked unless the existing contact-detail
opt-in is enabled. Older manually assembled renderer payloads without resolutions
infer accepted status only for source records explicitly nested under a combined
biobank; they do not infer unresolved matches.

The `merge-mucp`-only `--table-biobank-repeated-entries {empty,dtto}` option
defaults to `empty` and affects only combined-report tables with a canonical
biobank column. Scoped quantity, clinical/enrichment, eligible quantity
contribution, quantity-support, and free-text institution tables group by
biobank ID, ordered by country/name/ID; display names are never identity keys.
Institution lists, generic value/country tables and individual dossier tables are
not grouped. Standalone `describe` and `render-descriptive-report` behavior is
unchanged. Section 2.2 uses one logical country-grouped longtable, unknown countries
last, with gray banners and page-boundary top/bottom rules. A dedicated TeX mark
class tracks shipped rows; its output-routine continuation note identifies the
country/biobank at the end of the preceding page without frozen header macros.
Other grouped tables use independent per-bank blocks with a static,
wrapped literal continuation heading; it does not depend on mutable TeX state in
preboxed repeated headers. Compact blocks omit repeated generic column headings,
and each block closes with a booktabs `\midrule`.

Combined scoped-size rows are source-prefixed, show a verified unit or
`unit unclear`, and use a human collection scope or “Reported for this
submission.” Generic “Reported answer” wording is used unless source metadata
proves free-text or structured classification. Only source-owned full answers
that add context beyond the parsed amount are displayed; clipped index windows
are never rendered, and duplicate full answers for the same source/scope appear
once. Complete raw evidence remains in combined JSON.

`survey_descriptive.build_mucp_cohort_profile` counts unique selected MuCP participants
separately for canonical `donors`, `samples`, `aliquots` and `unit_unclear` units.
Donors, individuals and research participants share the donor analysis unit only
when verified; derived rows retain literal `source_unit`. Preserve scoped reported
totals and non-additive numeric mentions with provenance. Partition banks
into single reported scope, multiple scopes/values, qualified/bound, mentions-only
and missing states. Size bands include only a single unqualified reported scope;
they are not whole-biobank totals. Never sum scopes or Part B/Part C; never relabel
individuals as counts of deduplicated unique people. Samples and aliquots remain
separate; unsupported units, cases and FFPE blocks remain `unit_unclear`, not donors.
Quantity-index units are candidate metadata, not proof. Recover readable answer text
only from a same-record MuCP `text_field` evidence item with the same question ID and
compatible source-ID/locator references; each source ID must occur in that record's
`metadata.source_ids`. Keep clipped index context separate from recovered full
`raw_text`; expose the index classification/unit separately from verified
`answer_type`/`source_unit`; retain source question/references and recovery
diagnostics, and do not mutate native evidence. A complete source answer can prove
a literal unit only when its integer, relation and time agree with the mention;
disagreement retains the full answer with `unit_unclear` and a diagnostic. Immutable
reference sequences are accepted without mutation. Validate profile `reported_total`
units, values, relations and times against complete literal answers before assigning
canonical units or authoritative scoped-total status. Unsupported or disagreeing
projections retain raw text and typed metadata as unverified quantities.
Index classification alone cannot prove a unit. Discard code/year mentions from
size statistics.
Equal quantities from distinct source questions remain distinct scoped reports;
numeric equality does not establish that Part B and Part C describe one cohort.
Separate coverage of scoped reported totals from any classified numeric evidence.
Size-band ineligibility is not missing evidence: generic chart metadata accepts
three explicit `population_labels` for derived profile N/A/M semantics, while
survey summaries retain their existing labels. Missing profile evidence means
no classified numeric size quantity, not automatically no source answer.

Cross-survey UpSets use the existing external ComplexUpset bundle/validation
workflow and source-tagged sets. MuCP affirmative evidence and SO2 technology
access are complementary, not interchangeable. The `reported_checkbox_pattern`
projection includes present applicable negatives as all-zero membership rows,
excludes unknown/conditional/conflicting and incomplete-scope patterns with
diagnostics, and preserves the original state matrix. A dot means an affirmative
report in a represented scope; distinct-collection variation means at least one
reported collection, not universal availability. The pre-existing positive-event
projection remains available to other callers for compatibility. Technology
unknown and forced-Other-only exclusions remain unchanged.
The approved MuCP-only and mixed-survey UpSets use that classified checkbox
projection; positive-frequency bars intentionally remain available for
incomplete evidence. All-zero answered rows count toward the classified matrix,
whereas absent groups do not. Combined PDF output embeds validated UpSet PDFs
by default and adds the separately generated exploratory independence-deviation
PDFs only with `--include-upset-deviations`; those figures are not significance
tests. The external renderer still produces both PDFs. Canonical bundle material
includes reporting-policy and curated-presentation content hashes, so stale
figures fail validation before any output replacement.
Combined heatmaps use exactly seven curated version-1 presentation definitions,
including the exploratory legal pair. Each actual source category and exceptional
state needs an explicit short tick label; unknown categories fail before
publication. Source question IDs, full original question wording, category order,
counts and provenance remain unchanged. The combined view shows one short
subsection heading, labelled Y/X full questions and direct axis ticks; the
standalone `describe` heatmap renderer keeps its legacy presentation.
Clinical/phenotypic MuCP evidence is immediately paired
with all contributing SO2 terminology experience/standards answers, with missing
context explicit and links to full dossiers. The shared Libertine report preamble
must load `inconsolata` with `scaled=0.85` for monospaced text, including standalone
chart and individual dossier documents.
Unknown technology selections and forced Other-only selections must be excluded
with diagnostics, never projected as negative/all-zero concrete access vectors.
Compact supplemental and structured answer rendering must omit nested technical
locators as well as headings; extended evidence restores these presentation fields.

`survey-so2-directory.py merge-mucp` is a Directory-backed peer command. Its
analytical unit is one unique canonical Directory biobank selected by
`--join {inner,all-MuCP,all-SO2,outer}` (default `all-MuCP`). Survey-specific
statistics use only participants in that survey; shared analyses require both.
Existing `describe` remains Directory-free and response-row based.
See `docs/auxiliary-tools.md` for commands and operational safety.

- Validate MuCP Draft 2020-12 source schema locally and support only explicitly
  understood schema versions/answer states. Discover all structured questions
  and text fields from questionnaire metadata, including MuCP-only questions.
  Unknown substantive fields require explicit classification, never silent loss.
  Incremental-export `submission_label`, `source_page_range` and `source_links`
  are retained as lightweight response metadata, not interpreted as new answers.
  `ambiguous_mark` with raw null (for example a qualified parenthesized X) is
  ambiguous evidence, never an unconditional Yes or an unticked No.
- Immutable answer evidence carries survey, source row/response ID, question,
  raw answer, normalized semantics, answer_state, qualifier, scope and evidence
  references. Every derived observation and thematic group retains exact
  source-qualified evidence contribution links; validate
  them and the versioned combined output schema before serialization/rendering.
  Require retained source records and nonempty item locators. Where MuCP has no
  document locator, retain an exact input-JSON pointer/hash with an explicit
  document-evidence limitation, not an inferred document reference.
- Preserve duplicate/conflicting source records and collection scopes. No
  source-row join or record-count weighting determines cohort membership.
  A present applicable MuCP checkbox with `answer_state=unmarked` and raw null
  is a derived No under the versioned reporting policy, not a rewritten source
  state. Preserve its raw null, text, references and evidence ID; record the
  policy basis/version on interpreted evidence and the policy hash in combined
  inputs and coverage. Missing answer keys, not-asked, ambiguous and conditional
  entries remain unknown or conditional, never inferred No. Positive collection
  reports do not imply universal biobank availability or sibling inheritance.
  Established same-scope Yes/No is a contradiction, explicit distinct-collection
  Yes/No is variation, and unlinked differing responses have uncertain scope.
  B/C counts and collection totals remain non-additive without independently
  verified additivity evidence.
- Match through Directory APIs: reviewed overrides, exact IDs/collection parents,
  unique full emails, then unique exact institution/country or reviewed aliases.
  Check ownership against loaded excluded/withdrawn entities too. Ambiguous,
  conflicting and approximate candidates require review; country summaries are
  not automatically assigned to biobanks. Decisions bind source identity
  fingerprints, allowing unchanged decisions to survive unrelated source appends.
- Frozen SO2 findings require exact source hashes or a reviewed legacy binding,
  plus physical-row coverage checks. A matching filename is insufficient.
  Legacy name-certain findings require reviewed record overrides; even frozen
  exact matches must not bypass contradictory source evidence. National summaries
  allow reviewed collection-scope assignment only, never submission-scope acceptance.
- Linked source representations share an analytical scope only when exact
  workbook source, aggregate ID and source-row links prove that relationship.
  Labels, names and enclosing records alone never establish scope equivalence.
- Produce complete SO2 and MuCP descriptive catalogues independently of the
  thematic crosswalk. Themes distinguish comparable from complementary evidence
  and render each source contribution separately. Reuse shared categorical
  counting/chart selection and existing PGF/TikZ chart/layout primitives rather
  than duplicating `describe` or inventing EUS form metadata for MuCP.
- Basic categorical state/frequency charts remain available with explicit
  unique-biobank denominators. Approved heatmap/UpSet definitions use a default
  minimum of five classifiable observations and meaningful variation; this
  threshold is not a disclosure-control policy. Unknown/conflict/coverage
  diagnostics remain available even where a chart is omitted.
  Group frequencies count affirmative evidence even when scope coverage is
  partial; their answered denominator includes present applicable unticked No
  answers and excludes genuinely missing/unknown groups. Existing per-option
  unknown/partial, qualified-positive and varying-positive diagnostics remain in
  JSON and are not summed. Combined PDFs omit these scope-state coverage tables;
  generic standalone `describe` rendering keeps its existing default behavior.
- MuCP normalized checkbox evidence follows the versioned reporting policy:
  present applicable unmarked checkboxes mean No; missing, ambiguous and unasked
  entries remain unknown, and conditional entries remain conditional. The combined
  checkbox-pattern UpSet uses those classified states; incomplete positive scope
  coverage is excluded there without discarding known affirmative frequency or
  clinical evidence. Its no-dot meaning is limited to reported applicable scopes.
  Retain original states,
  unknown coverage, all-zero counts and scope caveats. Parent aggregate checkboxes
  must not masquerade as child specimen/data types. External R bundles bind
  input/cohort/definition/projection content and PDF hashes; normal runs never
  execute R and never modify an input asset directory.
  Validate actual matrix CSV bytes and generated renderer bytes, not merely
  copied manifest fingerprints; check every declared R prerequisite.
- Compose a coherent source-labelled combined report and optional standalone
  dossiers using the same fragments. Default PDF views exclude dedicated contact
  fields and mask recognizable email strings; opt-in contact inclusion does not
  alter original JSON evidence. Do not promise automatic anonymization of names
  embedded in arbitrary narratives. All combined artifacts remain sensitive.
- Validate path aliases before processing; serialize canonical JSON before compilation
  and publish all requested artifacts transactionally with sibling stages and
  rollback. Compilation or publication failure must not leave a partial output
  set. Retain deterministic country/ID/question/scope ordering and no credentials
  or duplicated embedded source-file bodies in combined JSON.
- Each combined and standalone MuCP dossier begins its answer material with a
  response-ID/source-filename inventory joined only from the validated payload
  manifest; display filename basenames, never manifest paths or embedded source
  content. Compact dossier answers use corrected normalized Yes/No/Unknown/
  Conditional semantics and retain qualifiers and distinct response scopes;
  extended evidence retains technical provenance. Combined statistics hide
  serialization prefixes without changing standalone `describe`. Curated group
  titles come from the versioned `so2_mucp_report_presentation.json` mapping.
  Serialization cleanup is limited to established leading prefixes; literal
  prose and quotations retain matching tokens. Inventory sources deduplicate by
  original response and source ID across assigned scopes. Compact evidence uses
  short source-tagged Question/Answer fields with complete prompts in the wide
  value column, keeping long answers pageable without repeating full prompts.
  Section 2.4 uses a two-column biobank/quantity-and-wording table with exact
  bound semantics. `reported_total` values retain their declared relation and
  original wording; narrative numeric mentions are explicitly unit-unverified
  and are not presented as authoritative totals. Never infer or relabel units
  from narrative text or `quantity_index` alone, and never mutate source JSON.
- `survey_mucp_quantities.py` produces the pure
  `MuCP.modality_quantities` summary from validated native evidence, exact source
  scopes and public question definitions in the versioned report-presentation
  file. A direct modality measurement requires an affirmed concrete structured
  answer whose *entire qualifier* states one nonnegative integer, a supported
  relation and an explicit sample, donor, individual, participant or aliquot unit.
  Aggregate/Other questions and narrative numeric co-occurrence are not direct
  measurements. Collection counts require a literal unit or a uniquely resolved
  count-cell/header witness; root B/C counts may use their documented
  individuals unit only for a complete numeric answer. Typed totals must agree
  with the source witness, including its exact relation. Resolved table count
  cells retain their bounds and original cell wording; a projected exact value
  must not override a source bound. Count-cell/field or header time is accepted
  only through an explicit `current`, `future`, `historical`, `cumulative` or
  `previous` label (`time: count` or `count/header (time)`); unlabelled counts
  remain temporally unspecified. Conflicting times, unknown headers, ambiguous
  table indexes and spanned count/header grids remain ineligible.
  `quantity_index` is an unverified inventory, never
  unit or attribution proof. Unsupported candidates retain explicit unlinked
  reasons, not zero-valued points.
- Validate projected/native totals against literal source units before applying
  canonical units to derived rows. Derived person counts use `unit=donors` and
  retain their original unit spelling in `source_unit`; samples and aliquots remain
  distinct.
  B/C individual-count fields may equate donor/individual/participant units;
  table/header comparisons remain literal. Complete field parsing supports grouped
  thousands, `mio`/`million`, `~`, and trailing `+`. A literal trailing-plus bound
  supersedes a projected exact relation only for these B/C fields with matching
  value and person unit; the original projection remains preserved and the profile
  records `source_suffix_bound_preserved`. Other relation mismatches remain rejected.
- Section 2.2 must show a source narrative containing its parsed counts only once,
  not once per numeric mention plus separate duplicate amounts. Literal evidence
  and all measurements remain in JSON. Presentation deduplication must retain
  distinct scopes and meaningful qualifiers, never imply numerical additivity.
- Section 2.4 includes linear, non-additive point views of known-unit observations
  excluded from exact stacks, with explicit bounds, time and B/C context. Different
  populations/counts remain separate, and identical repeated B/C assertions in one
  source scope share a display mark. These views never manufacture country totals
  or broaden material/data-type attribution; exact aggregation remains conservative.
- Each accepted observation retains the source response, exact scope, original
  wording, locator, evidence IDs, unit proof and Directory biobank country.
  Collection-size and submission-size context rows are separate from direct
  modality measurements; each count appears once with its same-scope modality
  links, never once per link. The extractor itself does not inherit sibling or
  parent counts, convert donation units, deduplicate equal amounts, or compute
  totals. The combined-only pure aggregate_modality_quantities reducer consumes
  those observations after extraction and retains raw observations unchanged.
  It reconciles repeated collection counts only within a biobank and a proven
  collection identity: a canonical Directory collection ID, an explicitly
  evidenced analytical-scope ID, or the same source-native scope within one
  response. Source-native collection IDs are response-scoped. Equal values or
  display names across different scopes/responses never establish identity.
  Agreeing same-scope repetitions count once and retain every quantity/evidence
  reference; conflicting values, relations or times are withheld with diagnostics.
  Direct modality measurements are grouped by proven reporting scope, modality
  and unit, retaining all agreeing quantity references and withholding conflicts.
  Different modalities within a scope are independent reporting views, not
  conflicting counts. Direct measurements remain separate from collection and
  submission totals and are never summed across different modalities into a
  generic country total.
  Multiple unlinked native submission scopes within a bank/unit/modality are
  ambiguous and withheld, including direct measurements. Explicit analytical
  identity can reconcile repeated representations; distinct analytical scopes
  are additive only with reviewed_distinct_reporting_scope evidence. Record IDs
  alone never prove independent populations. Across records, repeated native
  collection IDs, labels or physical source locators flag ambiguity, not identity:
  withhold their totals without merging the collections by name or value.
  Explicit parent_collection_id relationships select the topmost eligible
  reporting ancestor separately for each basis/unit/modality/time view. Covered
  descendants are excluded, never added to their parent; a child's modality
  remains eligible when its parent does not report that modality. Country
  collection totals select ancestors independently of modality links. Cycles,
  unresolved or ambiguous parents are diagnosed and withheld. Source scope
  members and relationship metadata remain available in contributions.
  Exact aggregation accepts only supported canonical units, unqualified
  reported_value relations, and current or unspecified time. Approximate and
  bounded values, future/historical/mixed-time evidence, and unclear units remain
  in excluded contributions with source references and reason codes. Explicit
  zero is a zero-valued segment; absent or wholly excluded evidence has a null
  total, never a fabricated zero. Collection country totals count each proven
  scope once regardless of its number of modality links. Modality totals may
  overlap because one collection can report several modalities and must not be
  summed across modalities. Counts with unidentified collections retain their own
  source basis; compatible chart views pool these only across independent banks,
  while collection values take precedence per
  biobank/modality/unit, and partial collection reporting is diagnosed.
  Each version-1 aggregate total carries unit, basis, temporal status, reported
  total, contributing biobank/scope counts, excluded count and bank segments
  containing value and source quantity IDs. Unknown or foreign bank, record,
  scope, modality-evidence or source-reference links fail validation rather than
  silently dropping a reported quantity.
  Coverage counts unique cohort biobanks with eligible source points by unit and
  linkage class. Report separate direct-modality, collection and submission-fallback
  quantity totals with explicit units, contributing biobanks/scopes and exclusions.
  Repeated proven scopes count once; ambiguous overlaps and conflicting quantities
  are withheld with diagnostics. Modality totals overlap and must not be summed.
  Missing measurement evidence is neither a zero amount nor a negative availability
  answer. The old quantity-coverage and checkbox scope-state matrices stay omitted.
  Combined exact-quantity PGF panels stack one segment per contributing biobank
  horizontally by Directory country, with countries ascending from the top.
  Country collection totals count each eligible collection once, regardless of
  type-link count. Country charts pool compatible collection counts and whole-biobank
  fallbacks across independent banks, never within the same bank. Material/data
  type views retain their actual IDs; actual type-specific measurements remain
  separate from counts of collections reporting that type. All material types share
  one linear view per compatible unit/measurement meaning/time, stacked by country;
  data-type views are separate. All combined stacked charts are linear only.
  Reporting-only `quantity_chart_views` extend the unchanged audited exact
  aggregates with distinct gray segments for uncertain source-owned counts.
  Preserve bounds, approximations, conflicts, timing and source references;
  gray segment widths use reported numbers, not estimated exact amounts.
  `confirmed_total`, `uncertain_total` and `display_total` remain separate.
  Starred display sums explicitly are not verified totals, because uncertain
  populations can overlap. Deduplicate proven source-local repeats, never
  equal amounts from different known scopes. Check actual plotted attribution
  per view, not merely eligibility before hierarchy/fallback reconciliation.
  Unknown-unit counts use separate panels. Raw numeric inventories (ages,
  dates, codes or unparsed narratives) stay in `uninterpreted_answers` and
  source tables, never become guessed count widths. Source coverage retains
  every MuCP record, including absent/nonnumeric counts without fake zeros.
  Type links must be source-proven; never copy counts to sibling collections
  or broaden actual type-specific amounts into whole-biobank country totals.
  Each compatible view shares global limits across pages; bank colors and
  legend order are stable. No separate duplicate point-chart appendix is added.
  Supporting rows state their actual country/modality selection or exclusion
  reasons, including bounds and time. Reconciled candidates are not labelled
  eligible merely because they precede view-specific hierarchy/fallback selection.
  Exclusion reason counts use the same view, unit, basis and time as each total.
  Source-proven collection count metadata enters profile reporting/missingness
  inventories through the same witness verifier as quantity extraction, but never
  manufactures a whole-biobank size-band observation.
  Chart row heights follow printable chart space and row count, not remaining
  page flow. No extra direct point/evidence chart appears in combined composition;
  source evidence remains in tables and JSON. Missing actual type-specific
  sample/donor counts are stated, not charted as zero.
  Total labels remain entirely inside the axis at both scales, including very
  small counts. Page-local legends use breakable tables with continuation context;
  never wrap the whole cohort legend in an unbreakable box. Bank table ordering
  uses an unescaped human-name key, not hyperlink targets or TeX escape syntax.
  Verified donor, individual and participant units share canonical `donors`;
  literal unit tokens, including singular header tokens, remain in `source_unit`.
  Samples and aliquots have distinct units. Quantity aggregation and replacement
  chart/table behavior are combined-only; `describe` is unchanged.
  Q point identifiers map to the bank's human name, stable submission ordinal,
  meaningful source scope, complete modality links, relation and time. Raw
  biobank/response/scope identifiers appear in this ordinary quantity table
  only under extended evidence; the dossier response-ID/filename inventory
  retains its separate provenance exemption. Chart tick and axis fonts retain
  the shared sans-serif family and non-serif numeric formatting, including
  fixed-point labels on logarithmic quantity axes. Exported
  curated heatmap documents include the short title and both full original
  Y/X questions from the same fragment as the combined report, exactly once.

### SO2 descriptive statistics report

- The standalone SO2 report ends with `QM vs traceability readiness`, implemented
  by `so2_readiness_scores.py`. Load versioned exact-choice rules from
  `survey-mappings/so2_2025_readiness_scores.json`; validate complete choice sets,
  field types and authoritative form UIDs against both the descriptive schema
  and actual manifest fields/choices, retaining their choice UIDs and requiredness
  in the saved model. If any readiness field
  is present, require all seven; schemas containing none remain unaffected.
  Score original source responses before `merge_descriptive_responses`, then
  attach vectors to its reviewed observation groups. Never score merged answer
  unions or fill one source vector from another submission.
- Components `a,c,l,u,d,p,r` map to `q_053,q_055,q_056,q_057,q_058,q_060,q_061`.
  Compute `T=(4*d+a+c+l+u)/8` and `Q=(2*r+p)/3`. Keep literal `p=.66/.33` for
  digital-manual/paper, not exact thirds. Match complete canonical answers with
  whitespace normalisation only. Custody uses configuration-order precedence,
  records every matched rule and flags differing selected scores. Unknown
  selections invalidate that component even if another selection is recognised;
  blank answers remain unscorable. ``Don't know -> zero`` is a scoring convention,
  not evidence of absent tracking.
- Agreeing seven-component score vectors collapse once. Differing vectors remain
  alternatives in one observation and never enter the main heatmap, even when
  totals happen to agree. Incomplete agreeing vectors remain visible but cannot
  enter a complete-pair heatmap. Unresolved identities remain separate observations.
  Associate group names/countries only with reviewed merge output, without contacts.
  Preserve raw source answers and component-specific status/precedence diagnostics.
- Public scoring rules must contain no response-derived reference block. Load
  optional private reference policy from ignored
  `survey-mappings/so2_2025_readiness_reference.json`. Its hash-bound source view
  may replay a reviewed matrix and documented blank override. Validate its exact source-row set, blank answer
  and golden matrix; fail if these disagree. Never mutate main source scores or
  reuse the exception by row number on another workbook. Other inputs get an
  ordinary source-submission view without overrides. Record the reference-only
  exception in the saved audit model and do not call either source view a
  unique-biobank analysis. Render/export only the deduplicated heatmap:
  neither the reference replay nor the original-submission heatmap belongs in
  the report or standalone chart directory. Preserve the source audit model
  for existing payload compatibility and independent validation.
- Bands are `[0,.2),[.2,.4),[.4,.6),[.6,.8),[.8,1]`. Heatmaps retain traceability
  rows (Very Low at top), QM columns (Very Low at left), Viridis, all 25 counts
  and a shared 0..35 reference colour scale, extended only when future counts
  exceed 35. Reuse native PGFPlots/standalone-vector-PDF publication. The score
  table groups by corrected country and institution, repeats headers, lists
  alternative source rows, all components, both totals and status; omit contacts.
  Explain formulas, weights and exploratory/non-certification interpretation.
- `readiness_scores` is a versioned self-contained model with embedded scoring
  rules/version/semantic digest, input SHA-256, source vectors, observation
  alternatives, diagnostics, bands, matrices and explicit denominators. Rerender
  recomputes every derived value and cross-checks all seven raw answers against
  independent `responses_summary.source_records`, exact observation membership,
  workbook checksum and authoritative form checksum. Missing independent evidence
  or explicit null values fail closed; inconsistent counts (including wrong JSON
  numeric types) fail. Preserve actual selected manifest fields independently in
  the enclosing `form_structure.field_bindings` and compare them to the model's
  copied bindings; changing mapping and embedded UIDs together must not bypass
  authoritative verification.
  Rerendering does not read private reference inputs. Keep conflicting alternatives on one table page.
  Legacy payloads without the field
  render unchanged. The
  local ignored fixture `tests/fixtures/so2_readiness_reference.json` retains
  seven answers and nine cached spreadsheet values per source; optionally replay
  all cached scores and 25 reference cells when that private dataset is available.
  Portable tests construct invented source vectors and independently check
  numerical formulas, boundaries, missingness, precedence,
  deduplication/conflicts, escaped multipage tables and transactional publication.
  Keep private source ZIP/XLSX and generated reports out of commits. MuCP and
  `render_statistics_sections` must remain unchanged.

- Raw survey exports/questionnaire archives and actual response-derived
  reference fixtures are local inputs, never publication artifacts. Retain
  generated form JSON and data-free schemas/rules in Git. Default standalone
  identity loading prefers the ignored local reviewed mapping and otherwise
  uses `so2_2025_response_identities.example.json` (empty reviewed decisions).
  Explicit `--response-identities` failures must not silently fall back. Keep
  source-bound MuCP quantity review data local; its absence is already supported.

- Association heatmaps are configured only through `survey-mappings/so2_2025_association_heatmaps.json`. Review each definition with its question IDs, form UIDs, category order, interpretation text, and regression evidence. The CLI validates the registry before publication; payloads record both the registry file hash and canonical definition digest. Every categorical axis displays actual answer labels, never numeric keys or R1/C1 lookup legends. Optional `presentation` metadata supplies complete canonical-category-to-display-label mappings (`row_tick_labels`, `column_tick_labels`) and one-to-three manually reviewed title lines (`row_axis_lines`, `column_axis_lines`). Validate nonblank distinct labels and exact category coverage; preserve presentation in payload definitions and their digest. Shortening must be semantic and reviewed, never naive Python truncation. TeX wraps ticks in bounded boxes and uses semantic question titles. Full canonical answers/order/counts/denominators remain unchanged. Existing payloads without display metadata stay accepted and show their full actual categories. Mapping-based combined-survey layouts remain compatible. Do not add contact/free-text fields, including `q_111`, infer willingness from contact completion, or publish small-cell panels without a separately approved complementary-suppression policy.

`survey-so2-directory.py` also provides a standalone descriptive-statistics
workflow. It is intentionally separate from the Directory-consistency workflow
above and must not be added as a section of its findings report.

- The CLI consists of `export-eus-form-json`, which deliberately regenerates
  the checked-in form manifest from the authoritative EUS archive, `describe`,
  which reads that JSON manifest and one or two response exports before writing
  a versioned descriptive-statistics JSON payload with optional TeX/PDF output,
  and `render-descriptive-report`, which renders TeX/PDF from that payload
  without re-reading source artifacts. `describe` and rendering must not load
  the EUS decoder or `directory.py`, request credentials, require the
  entity-resolution mapping, or create findings/update JSON.
- `describe` uses `so2_response_merging.merge_descriptive_responses` before
  descriptive statistics. Merge only a shared explicit valid biobank ID or a
  reviewed offline identity in `survey-mappings/so2_2025_response_identities.json`.
  Reviewed row mappings are bound to the original XLSX SHA-256, never reused by
  row number on a different file. No live Directory access or fuzzy/name-only
  grouping is allowed. Distinct biobank IDs at the same institution stay distinct.
  Unresolved submissions remain separate observations: the resulting count must
  not be claimed to be an established count of unique biobanks.
- Preserve all source records, literal answers, original countries, identity
  decisions and country corrections in `responses_summary`. Agreeing structured
  answers count once; blanks may be filled from another submission. Conflicting
  single-choice answers become an explicit `Conflicting answers` category.
  Multi-choice selections are unioned with question-level differences flagged;
  contradictions remain visible. Distinct substantive free text is retained;
  apply the existing empty-placeholder filter separately to each contribution,
  so combining `None` with real text does not resurrect `None` in readable tables.
  Original placeholder answers still remain in source evidence. This reports
  evidence across submissions, not uniformly true collection scope. Use merged
  observations consistently for charts, heatmaps and UpSet vectors. The reusable
  `build_descriptive_payload` remains row-based unless given a merged workbook,
  so combined-survey aggregation does not change accidentally.
- The unnumbered `Responses Summary` follows Abbreviations and gives received,
  merged and resulting observation counts, duplicate groups by country/institution
  and source rows, the merge protocol, conflict count and unresolved-identity count.
  Retain original total/nonblank/excluded row counts, workbook hash, worksheet,
  header row, schema and identity-mapping hash. Source validation must precede
  any merging so duplicate multiplicity is not hidden.
- Standalone descriptive reports omit observed-minus-expected UpSet images.
  Existing bundle deviation files remain generated/validated for compatibility,
  but are not embedded. Only q_018 is generated 16 inches wide with a taller
  matrix share (`height_ratio=1.5`) to separate its set labels and embedded
  rotated 90 degrees, bounded by printable width/height. Other figures retain
  their orientation. Regenerate external assets when merged vectors change.
- The current SO2 XLSX envelope has service metadata in row 1 (`Alias` /
  `SO2_2025`), export metadata in row 2 (`Export Date` / timestamp), a blank
  row 3, and column headers in row 4. The reader must validate this envelope and
  configure its header row explicitly. Preserve alias and export date as payload
  provenance; never count service rows as questionnaire responses. A later survey
  version may declare a different validated envelope in its descriptive schema.
- A versioned descriptive-report schema declares source worksheet/header, every
  question's source column(s), question type, display label/order, allowed and
  canonical categories, optional multi-select delimiter and category aliases for documented literal-value normalisation, optional applicability
  rule, optional mutually exclusive categories, and optional parent question for
  free-text follow-ups. A free-text follow-up may declare `parent_context_values`,
  mapping each parent column to only the canonical structured selections that
  semantically enable the follow-up. It never drops substantive child text:
  retain raw parent evidence in JSON and diagnose a nonmatching parent selection.
  Readable reports omit parent context by default; `--include-parent-context`
  shows complete raw parent answers, never the semantically filtered subset.
  Omit this metadata only when no
  safe answer-based restriction exists. Applicability values must belong to the referenced
  structured parent question; exclusive selections must belong to the question
  that declares them. Account for every
  source column as a reportable question/subquestion, respondent-context field,
  or explicitly excluded administrative field with a stated reason; reject an
  unclassified source column. Do not infer multi-select semantics solely from
  question wording or semicolons in an answer. A declared parent value must be
  read from the same row, never inferred from column adjacency. Retain
  zero-count declared categories and entirely unanswered questions. Unexpected
  values or contradictory declared selections must stay traceable as diagnostics,
  not silently become missing or disappear.
- Support at least `single_choice`, `multi_choice`, `ordinal`, and `free_text`
  question types. For every structured question report total included rows
  (`N`), answered rows (`A`), and blank cells (`M = N - A`). A blank means
  only blank, not necessarily an eligible nonresponse. Where a verified
  applicability rule exists, report eligible-unanswered, structurally skipped,
  eligibility-unknown, and out-of-route answered rows separately; otherwise
  state that applicability is unknown. Never infer routing from observed counts
  or discard out-of-route answers. Single-choice counts must reconcile exactly
  with `A`. Category aliases may normalise documented source spelling variants to their declared canonical category; the raw workbook remains the source evidence. Multi-choice values are deduplicated within a response: every
  selection label is `n (n/A percent of answering rows)`, while Missing is
  `M (M/N percent of all included rows)`. State both bases, render an undefined
  percentage as `N/A`, and never divide by total selections. Individual
  selection percentages cannot exceed 100 percent, though their sum can. Keep
  blank, `No`, `Don't know`, `Not applicable` and `Planned` distinct.
  Numeric bands are frequency categories, not data to average. Matrix
  subquestions with ordered frequency answers are `ordinal`, even if a nearby
  heading says “select all”.
- Every structured question has a literal respondent-level contribution table in `--long-report`, with `Value`, `Country`, `Institution`, and compact grouped institution evidence ordered by declared value order, then country and institution. The descriptive schema declares the
  shared country and institution source columns. A multi-choice response appears
  once for each selected value; a non-answer appears once under `Missing`.
  Keep missing country/institution cells visible as `Missing` rather than
  dropping their response. Preserve repeated display rows literally and mark each
  row when its normalised country/institution appears in multiple submissions;
  these are suspected repeated responses, not sufficient identity evidence for merging. For an
  answered-only pie variant, retain the Missing contribution block and mark it
  as excluded from that chart. Contribution tables are respondent-level evidence:
  they reconcile with the chart's value counts but must never be summed across
  questions.
- Free-text tables list every substantive nonblank answer with a two-letter ISO country code, the reported institution, response text, and same-row declared parent answer, including a missing or unexpected parent value. Omit source-row provenance from the readable table but retain it in JSON. Put the fixed parent question or questions under the `Parent context` table header and put only same-order parent values in cells; reject a payload which mixes parent-question columns across rows. Omit the parent-context column only when every displayed row has no configured parent answer. Suppress only explicit empty placeholders such as `None`, `N/A`, `No`, or `Nothing` after whitespace normalization. Render HTTP(S) URLs as a short `link` hyperlink. Flag inconsistencies without suppressing text. Report
  answered and blank counts and render an explicit `No text responses` section
  when empty. Do not deduplicate identical text, infer parent answers, or treat
  volunteered comments as prevalence estimates. Do not incidentally copy emails
  or other identifying values into unrelated tables; a field is listed only when
  it is the answer being reported.
- The rendered report repeats full source provenance and shows a compact, breakable complete `Question identifier:` line, `N`, `A`, `M`, manifest-derived response type, and mandatory/optional declaration for every question. It must not display the internal applicability diagnostic. It must define `N`, `A`, `M`, `oAR`, and `oIR` immediately after the table of contents; bar labels use the abbreviated percentage bases. Standalone chart documents repeat the question, denominator, unit,
  and missingness context so they remain interpretable outside the report.
- Descriptive-report TeX must use `scrartcl`, `\KOMAoptions{parskip=half}`, and
  zero paragraph indentation. Do not use `\\` for ordinary paragraph spacing:
  use `\par`, `\vspace`, or `\vspace*`; retain `\\` only where a table row or
  deliberate premature line termination requires it.
- SO2 joint-profile figures use `so2_response_profiles.py` for the approved legal
  (q_063..066), organisational (q_068..071), and collaboration (q_073..076) matrix
  groups. Align contribution identities, not institutions or marginal counts;
  require all four verified single-choice matrix items with one parent, unique
  positive source-row identities, identical observation sets and exact agreement
  with question N/category counts. Reject inconsistent evidence before publication.
  Every analytical observation belongs to exactly one full four-answer profile;
  retained Missing/conflict/not-applicable states are never imputed or scored.
  Equal vectors are aggregated with source-row membership, ordered by decreasing
  frequency then declared category ranks; profile IDs are local ranked identifiers.
  Only the standalone SO2 renderer adds the derived `response_profiles` JSON field.
  For each group, retain existing charts, then insert top12 and complete joint
  figures under its section and export them through existing chart publication.
  Percentages/coverage use all observations N; the two figures share a frequency
  scale. Complete charts fit printable width and at most 0.82 textheight, leaving
  room for section heading and file path; dense plots may need zooming. Category
  colours encode ranks without equal-distance assumptions. Generic/combined MuCP
  rendering must not acquire these graphs or altered statistics.
- Use native TeX PGF/TikZ, primarily `pgfplots`, for report charts. Python computes
  statistics and emits reusable chart fragments; TeX renders them in the report.
  Horizontal zero-based count bars are the default for category comparison and
  are mandatory for multi-choice questions: each selected value has a bar with its `n (percent oAR)` label, a fill-matching outline, adaptive label-row spacing, and explicit vertical margin below the final bar; `Missing` is a visually distinct separate bar
  even when zero. Long categorical charts must fill the printable text height before splitting into continuation charts, while retaining an identical zero-based horizontal scale. Standalone SO2 `describe` and `render-descriptive-report` show donut charts for small, readable, non-overlapping single-choice distributions, preserving the existing pie slices, colors, counts, percentages, labels and missing-answer variants, with a center hole at half the outer radius. Every external label retains its same-colour leader line and swatch. The `--max-piechart-ratio WIDTH:HEIGHT` option and numbered-label fallback also apply to donuts. Single-choice matrix controls retain their parent sections, row subsections and denominator variants.
  Standalone SO2 bars use decreasing count order globally before pagination,
  including ordinal and missing/exception categories; equal counts preserve source
  order and zero-valued declared levels remain visible. Canonical JSON categories,
  statistical calculations and denominators are unchanged. MuCP/combined reports
  keep their existing pies and bar ordering: shared helper defaults must remain
  unchanged and standalone presentation must be explicitly opted into by its caller.
  Multi-choice data must never use donut/pie charts. SO2 reports omit observed-minus-
  expected UpSet figures and rotate only q_018 (interoperability) 90 degrees on a
  dedicated page. Existing deviation assets remain validated for bundle compatibility;
  combined-survey UpSet generation is unaffected.
- `describe --output-chart-dir DIR` additionally renders each report chart from
  the same PGF/TikZ fragment as a standalone vector PDF. The report displays the
  relative output path below its corresponding embedded chart. The directory must be new or empty by default (or explicitly replaced with `describe --overwrite`), and chart filenames must use a stable question ordinal,
  sanitized identifier and variant suffix. Every standalone chart PDF retains
  the full question identifier, denominator, unit and missingness note. The
  descriptive payload records report-relative chart paths; no PNG export is required
  initially.
- TeX-only output writes a self-contained report source with embedded chart TeX
  and does not require a TeX compiler or render standalone chart PDFs. PDF and
  standalone-chart builds must stage every generated chart asset in a temporary
  compilation directory, then publish from hidden sibling paths on each target
  filesystem so cross-device publication cannot fail with `EXDEV`. Descriptive
  file outputs must be new by default and the chart directory must be new or empty by default. `describe --overwrite` may replace its existing JSON, TeX, PDF and chart directory only after successful staging. Any
  write, compile, or publication failure must roll back all outputs from that
  invocation. Those builds must
  fail clearly if a referenced asset or the `xelatex` dependency is
  unavailable. Report PDF rendering must run XeLaTeX twice so table-of-contents links resolve; they must not produce partial PDFs.
- Every function in `so2_descriptive_report.py` and `survey-so2-directory.py` must document its purpose, every input parameter's semantics, every return value's semantics, and raised user-facing exceptions where applicable. The descriptive-report tests enforce the parameter/return documentation contract. Validate external
  workbook/schema/report-payload assumptions with actionable `InputError`s; use
  assertions only for already-validated internal invariants.
- Tests must cover all-row inclusion without Directory access, blank rows,
  question-type semantics, explicit/unknown applicability, parent/free-text rows,
  repeated institution submissions, duplicate selections, embedded delimiter
  text, unexpected/contradictory categories, unclassified/missing schema columns,
  output collisions, Unicode/TeX escaping, legacy descriptive payloads,
  denominator labels and chart-asset staging. A real XeLaTeX rendering/layout
  check is conditional on the compiler being installed; otherwise validate
  generated TeX and report the missing dependency explicitly.

### SO2 EUSurvey authoritative form and response inputs

The SO2 descriptive-statistics workflow separates EUSurvey configuration
extraction from ordinary report execution. The committed EUSurvey archive
`survey-mappings/SO2_2025-u65uym7bs7d8bfs7j7hpcwoc1y.eus` is form-configuration
provenance only; it must never be treated as a response source. The committed,
reviewable JSON manifest `survey-mappings/so2_2025_form.json` is the runtime
form contract. XML is the preferred response source, while XLSX remains a
compatibility response source. `describe` must require the JSON manifest and
exactly one answer source, or both answer sources for strict cross-validation.

- `export-eus-form-json` is the only command that decodes EUS Java
  serialization. It must read exactly one `survey-active.eus` member through a
  bounded, data-only decoder and deterministically generate the JSON manifest.
  It must not instantiate EUSurvey application classes, inspect unrelated
  account data, or silently fall back to `survey.eus`, which may contain draft
  changes. Normal descriptive reporting and Directory-coherency analysis must
  not import the decoder or require `javaobj-py3`.
- The generated manifest must record its schema version, generator version,
  EUS archive SHA-256, active-member SHA-256, survey UID/alias, and the complete
  normalized form model. The model includes field UID, title, position, type,
  `optional`, readonly/hidden state, choices, choice dependencies, and matrix
  layout. Regeneration with the same EUS input and generator version must be
  byte-stable. A changed checked-in manifest must be reviewed alongside the EUS
  provenance hash change. `optional=False` means mandatory. Matrix-row labels
  inherit their containing matrix's status unless EUS explicitly provides
  independent row constraints.
- Form field UIDs in the manifest are the canonical identity. XML field and
  choice IDs, types, labels, choice ownership, matrix rows/scales, and
  dependency targets must reconcile with the manifest. Unknown or dangling
  identifiers, incompatible types, malformed matrices, unsupported routing
  structures, manifest-version mismatch, or manifest integrity mismatch must
  fail before response statistics are calculated.
- The XLSX adapter must use a versioned explicit header-to-form-UID mapping. It
  must account for every meaningful XLSX header as a field, matrix row,
  respondent-context field, or documented transport metadata. It must map
  choices only through documented export transformations; ambiguous headers,
  delimiters, formulas, truncation, or unknown values must fail rather than use
  fuzzy label matching.
- The XML adapter must resolve every `qid` and `aid` against manifest-owned
  fields and choices. An XML response element with an `aid` is a selection even
  when its text is empty. Parsing must reject external entities and preserve
  literal free-text evidence without case-folding or placeholder-to-blank
  conversion.
- Each adapter emits the same complete UID-based canonical response vector,
  including respondent-context fields, matrix coordinates, unordered
  multi-choice selections, explicit unanswered values, and duplicate response
  multiplicity. Source-specific raw evidence remains available for diagnostics.
- If XML and XLSX are both supplied, both must independently validate against
  the manifest and their complete `Counter(response_vector)` values must match
  exactly. Matching record counts, marginal totals, institution identities, or
  row order are insufficient. Differences block JSON, TeX, and PDF publication
  and must report affected field UIDs and surplus-vector multiplicities without
  inventing a respondent pairing. Existing outputs must remain intact on
  failure.
- Requiredness is interpreted with routing. A mandatory field that was not
  shown is not a missing answer. Out-of-route answers remain diagnostics unless
  the validated manifest routing semantics prove them invalid. Dependencies
  must be represented as structured Boolean expressions, preserving EUS AND/OR
  and matrix/container semantics rather than flattening them into labels.
- Descriptive payloads record manifest/archive/member/XML/XLSX hashes,
  generator and normalization versions, source coverage, validation status,
  field metadata, and structured routing expressions.
  `render-descriptive-report` must render that self-contained payload without
  reopening inputs.
- Every report question must show manifest-derived response type and status:
  `Mandatory`, `Optional`, `Mandatory when shown`, or `Optional when shown`.
  Conditional fields must also show a human-readable `Shown when:` expression.
  Do not infer either type or status from question wording, XLSX blanks, or
  observed response frequencies. Readonly/hidden/validation metadata remains in
  payloads and is printed only where it materially changes interpretation.
- The report introduction must summarize the validated active-form manifest and
  selected answer source(s), field counts by type/status, input hashes, and
  XML/XLSX cross-validation result. Existing chart denominators and row-level
  statistical semantics remain unchanged.
- Tests must cover active-versus-draft selection, corrupt/oversized archives,
  deterministic manifest serialization, manifest provenance/integrity checks,
  UID collisions, unsupported classes, mandatory/optional flags, nested AND/OR
  dependencies, matrices, XML reference validation, XLSX mapping/value
  validation, semantic XML/XLSX equivalence, duplicate response multiplicity,
  mismatch publication rollback, and TeX/PDF metadata rendering.

#### Optional descriptive UpSet assets

`survey-mappings/so2_2025_upsets.json` is the sole approved registry for
descriptive UpSet figures. Numeric selectors such as `q_009` resolve to exactly
one full schema question identifier. `build_descriptive_payload` retains one
canonical vector for every included response to each multi-choice question;
rendered contribution rows are never used to reconstruct vectors. The vector
contains source row, country, institution, state (`answered`, `missing`, or
`inapplicable`), and declared selected categories.

`export-descriptive-upset-r` emits CSV/R assets and an input manifest. A
nonempty `describe --upset-assets-dir` must have matching input/output manifests,
the exact canonical payload/registry hash, the complete approved definition set,
and every declared PDF. Missing, stale, incomplete, or unsafe bundles fail before
report publication. `describe` never modifies the supplied assets directory.


## Preserved Documentation Discrepancies

The inherited analysis-tool paragraph describes three technology UpSet outputs; newer descriptive/combined contracts omit deviation pages by default. These are distinct paths; do not use the historical generic statement to re-enable descriptive deviation pages. The relocated historical asset guide describes deviation bundle files, which are retained for compatibility, not necessarily embedded. The specific SO2 descriptive and combined presentation contracts govern embedding.

The inherited agent rule prefers latexmk for findings reports while the inherited analysis-tool specification requests direct xelatex. No compiler behavior changes in this migration: inspect the affected command and its regression tests before changing that contract. Descriptive reporting continues its documented two-pass xelatex path.
