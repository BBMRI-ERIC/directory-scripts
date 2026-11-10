# Vocabulary Migration And MIABIS Conformance

Status: design draft for approval; no implementation authorized by this file.

## Purpose And Agreed Boundaries

Support migration to updated Directory dataset/service vocabularies, warn data
managers about deprecated values, and independently assess the Directory's
implementation of MIABIS vocabularies. Explain operational consequences in the
Data Manager Manual, including the removal of network inheritance.

Confirmed decisions:
- Reviewed GUIDANCE JSON belongs in directory-scripts, so QC runs standalone.
- The Manual contains expanded LaTeX guidance, not the mapping database. Source
  comments may reference JSON guidance IDs and upstream evidence.
- Upstream GitHub commits describe changes; they are not assumed to provide a
  complete semantic migration crosswalk. Reviewed guidance supplies that value.
- A separate Python conformance checker may read schemas and reference ontology
  definitions, but never biobank, collection, service, contact or fact records.
- Implementation discrepancies belong in the Manual and standalone audit output,
  not in ordinary Directory-data QC findings or updater proposals.
- Analyze additional data-consistency checks; do not silently implement unapproved
  semantic rules merely because vocabulary names appear related.
- Using a deprecated value is an ERROR, even when the Directory still accepts
  that value for backward compatibility. Reporting an error does not authorize
  replacing the value automatically.
- Manual text, QC messages and audit reports must use plain, concrete language:
  explain what changed, what is wrong, what to do and what information is missing.

## Existing Evidence

Read-only investigation retrieved ERIC and DirectoryOntologies metadata and
relevant ontology terms on 2026-11-05. Detailed local evidence is preserved in
the schema-review cache; that runtime cache is not a repository dependency.

- ERIC exposes 19 tables. Its 287 business fields match the checked upstream
  entity model for field identities/types, required flags, keys and references.
- DataCategories changed from 15 to 24 terms. Relevant upstream changes are
  82fe9dd831cc64455770598c810998cb105972b8 (October 8),
  27a725e3a594e6e26d4ad27352e4451f3cf9f098 (October 26), and
  68d9d8d89130dbe0b8ce6795585c0c7a0c4f174e (October 29), in
  molgenis/molgenis-emx2, data/biobank-directory/ontologies/DataCategories.csv.
- ServiceTypes changed from 62 to 37 names in upstream
  d96bb75b3ec62552e6b32e886bc43bcff95b5190 (September 18). Services still has
  17 business columns; the six ServiceCategories predate this change.
- The retained IMAGING_DATA, SURVEY_DATA and NATIONAL_REGISTRIES terms are
  explicitly deprecated in their definitions, not in a dedicated status field.
- Existing cached ERIC data still uses old names. Historical cache data must not
  be mistaken for the current production schema or proof of current violations.
- Network inheritance removal is evidenced by upstream
  e1319d600d95a445180deac3b8af4db06837fe73: combined_network was removed from
  Biobanks/Collections and parent_network from Networks. Upstream commit date
  and the Manual's revision-log date are different kinds of provenance.
- Official MIABIS repository BBMRI-ERIC/miabis currently resolves to
  272d05e792e312f1fe56e24eac37d43ce9376bf1. At that snapshot, all lists.md has
  14 Dataset Type entries and 32 Service Type entries. Core/V3 and the service
  component are available, but no GitHub release objects establish a v4 release.
  A Directory commit's v4 claim must not be mistaken for normative release proof.

## Approaches And Selection

1. Infer everything from live ontology descriptions: avoids curated guidance,
   but cannot recover deleted terms or reliably infer semantic replacements.
2. Maintain mappings in LaTeX and export JSON: creates a Manual build dependency
   and was explicitly superseded by the user.
3. Selected: live/pinned upstream definitions plus reviewed guidance JSON in
   directory-scripts, expanded LaTeX explanations in the Manual, and a separate
   metadata-only implementation audit. JSON contains guidance and evidence, not
   a parallel copy of the entire vocabulary.

This is a cross-repository project, not just a new warning condition. Existing
CollectionContent predicates and the recently regenerated check catalogue must
not be reimplemented under competing warning IDs.

## Guidance Data Contract

Proposed files:
- vocabulary-guidance.json: bundled reviewed guidance, located relative to the
  installed script/module file, never invocation cwd or a sibling Manual clone.
- schemas/vocabulary-guidance-v1.schema.json: versioned local artifact contract.
- vocabulary_guidance.py: validated loading, selection and human explanations.

### JSON Organization

This is one versioned document with the following top-level members. It contains
reviewed guidance, not entity records, full vocabulary mirrors or runtime results.

| Member | Contents |
| --- | --- |
| `schema_version` | Integer contract version, initially 1. |
| `sources` | Map of stable source IDs to immutable GitHub repository/revision/path/section references and content hashes. Distinguish Directory history from MIABIS specification sources. |
| `production_checks` | Observations with stable ID, target URL, schema, UTC checked time, schema and ontology hashes, server-reported build, and source revisions whose contents match. A content match is not a deployment claim. |
| `expectations` | Reviewed software release and independent model/ontology reference IDs. Each reference component declares expected, known-older and known-newer source IDs; these are not minimum capability requirements. |
| `migrations` | Array of guidance entries keyed by stable ID: old Directory terms, replacement options, conditions and curator actions. |
| `miabis_bindings` | Array of reviewed comparisons between a MIABIS concept and Directory terms, including unresolved/missing concepts and Directory extensions. |
| `structural_changes` | Array of non-vocabulary guidance, initially removal of network inheritance. |
| `manual_sections` | Map of logical section IDs to LaTeX labels, readable titles and verified publication references, or explicitly unpublished status. |

References between members use stable IDs. Source records store a full commit
SHA, path and SHA-256; line/section locators supplement rather than replace those
identities. Large downloaded files and complete commit diffs remain in caches,
not embedded in this JSON. Never include credentials, curator contacts or entity
snapshots. `production_checks` are reviewed maintenance observations, not a log
appended on every QC invocation.

### Migration Entry

Every migration contains these fields:

- `id`: stable guidance identity, independent of a check ID or changing label.
- `table`: `DataCategories` or `ServiceTypes`; `entity_fields`: explicit consumers
  such as `Collections.data_categories` or `Services.serviceTypes`.
- `previous_terms`: nonempty list of exact old stored names. Group names only
  where every member has the same advice; term membership must be unambiguous
  within an applicable source context.
- `applicability`: `reviewed_reference_ids`, identifying definitions against which
  advice was reviewed. Relevant term fingerprints, including proposed targets,
  must agree before advice is displayed; unrelated new terms do not invalidate it.
- `history`: `before_source_ids`, `after_source_ids` and `production_check_ids`.
  These document the transition and production observations, not runtime gates,
  arbitrary version ranges or assertions about all future deployments.
- `status`: `deprecated`, `removed`, `replaced`, `restored` or `changed_definition`,
  describing the evidenced transition. This alone never authorizes a runtime
  accusation about records from an incompatible snapshot.
- `replacement_options`: zero or more objects, each with `terms` (exact target
  names), `relationship`, `basis`, `conditions`, `explanation` and `evidence_ids`.
  Relationships are `equivalent`, `target_broader`, `target_narrower`, `split`,
  `combination` or `unresolved`, always old-to-target. Basis is `upstream_explicit`
  or `reviewed_recommendation`. A split is a set of options to examine, not an
  instruction to add every target.
- `actions`: ordered objects with `kind` and `text`; kinds are
  `replace_known_value`, `inspect_existing_information`, `ask_curator`,
  `collect_missing_metadata` or `no_safe_replacement`. These are human advice,
  not executable updater instructions.
- `information_needed`: concrete unanswered questions; `explanation`: short
  readable overall rationale; `evidence_ids`: supporting source IDs/locators.
- `review`: `state` (`accepted` or `needs_review`), `reviewed_on` (date or null)
  and `note`. Acceptance means repository guidance was reviewed, not that MIABIS
  endorsed the mapping. Unresolved advice can be accepted as such.
- `manual_section_ids`: references to detailed Manual explanations.

For example, an IMAGING_DATA entry has three replacement options: Body image,
Whole slide image and Photo image. Each is narrower than the old generic term
and conditional on the collection actually containing that image type. Its action
is to inspect imaging metadata and select the supported types, not automatically
add all three. MEDICAL_RECORDS to Clinical dataset is instead a broader-target
recommendation; OTHER must retain an unresolved outcome if narrowing to Other
sample-derived dataset cannot be justified. Do not mark these examples as exact
equivalences merely to complete the file.

An unresolved entry uses an empty replacement list, `no_safe_replacement` advice
and a precise `information_needed` question. A service term without a safe
successor must not disappear or be silently mapped to Other service.

### MIABIS Bindings And Structural Changes

Each `miabis_bindings` record contains `id`, `miabis_concept` (source ID plus
stable code if available, otherwise section/table row identity), `directory_terms`
(table/name references), `relationship`, `explanation`, `evidence_ids`, `review`
and `manual_section_ids`. Relationships are `equivalent`, `directory_broader`,
`directory_narrower`, `missing_in_directory`, `directory_extension` or `unresolved`.
For extensions the MIABIS concept is null; for missing concepts Directory terms
are empty. These are comparisons with MIABIS, not historical migration rules.
Every reference and implemented term must be accounted for by bindings or an
explicit unresolved comparison result; do not duplicate full definitions here.

Each `structural_changes` record contains `id`, `affected_fields`, `change`,
`before_source_ids`, `after_source_ids`, `production_check_ids`, `actions`,
`information_needed`, `explanation`, `evidence_ids`, `review` and
`manual_section_ids`. The network entry identifies removed combined_network and
parent_network fields and explains explicitly recording confirmed membership;
it does not express network removal as a vocabulary substitution.

### Consumers And Maintenance

QC determines declared deprecation from the applicable reference definitions and
uses accepted migration entries only for supported explanatory advice. It does
not use MIABIS bindings to generate routine data errors. The standalone checker
uses bindings, source history and observed metadata. The Manual uses all three
guidance sections, with reviewed expanded prose. Entries needing review remain
visible to maintenance/reporting but must not supply asserted replacement advice.

Validation checks referential integrity, complete historical-term coverage,
directional relationship names, per-context conflicting mappings and Manual
references. Upstream changes flag affected entries for review; neither fetching
new sources nor a normal QC run rewrites or approves the curated document.

Each entry has a stable ID, vocabulary/table, previous term identity, applicable
source versions/snapshots, status, replacement options, meaning relationship,
conditions, additional-information requirements, explanation and evidence.
Evidence includes repository URL, immutable commit, file and line/section
locators; use stable term/code anchors where available and file/content hashes
to detect source changes. Do not rely on mutable master URLs or line numbers alone.

Relationships distinguish exact naming changes, broader/narrower concepts,
splits, combinations and unresolved cases. Actions distinguish re-expression of
known metadata, review of existing source information, curator clarification and
additional metadata acquisition. They do not order new scientific assays.
An entry must say whether a replacement is explicitly upstream-defined or a
reviewed recommendation. Never turn a split into an assertion that both parts
exist. Preserve qualifications and uncertainty.

Examples to cover initially include the old physiological/biochemical combined
category, OTHER versus Other sample-derived dataset, generic versus specific
imaging, and retired service names with no one-to-one successor. Exact-renaming
guidance must still be evidence-backed rather than inferred from string similarity.

Initial coverage is complete for the identified migrations, not just the examples:
every removed/replaced previous DataCategories name, all three retained deprecated
categories, and every previous ServiceTypes name must have an explicit guidance
outcome. Equivalent cases may share one record, but coverage tests must account
for every old term. Include a structural-change guidance record for explicit
network membership, linked from the Manual. Do not require a guessed replacement:
an unresolved outcome with the specific information needed is valid coverage.

The implementer prepares evidence-backed guidance and expanded prose for normal
human review in the two repositories, supported by independent technical review.
The extractor must not present its own interpretation as an official mapping.
Unsupported equivalence claims remain unresolved; neither completion nor running QC depends
on persuading an external body to supply a missing crosswalk. Any proposal to
assert an uncertain mapping as definite requires separate human approval.

Runtime QC never modifies the JSON or learns new mappings. Maintenance retrieves
upstream source changes programmatically and reports guidance entries needing
review; it cannot silently approve semantic mappings. Offline runs use bundled
guidance and explicit provenance-bearing reference caches.

## Reconstructing Changes From GitHub

The Directory API shows the model and vocabulary available now; it does not
establish how they changed. Use both the API and the official Directory model's
GitHub history. Looking only at the first and last versions is insufficient.

Fetch the complete relevant history within explicitly pinned revision ranges for
the model and ontology files, including staging-model counterparts when relevant.
The initial history must include the 2025 network-inheritance removal and the
2026 DataCategories/ServiceTypes changes. Resolve references to immutable commits;
follow file renames and handle paginated results without silently dropping pages.
Process changes in repository order, not solely by commit date.

Record each relevant step: additions, removals, renames, changed definitions,
splits, combinations, deprecation changes and restorations. For example, the
temporary removal and subsequent restoration of Biological samples must not
disappear merely because the first and last versions both contain that concept.
A removed name plus a new name is not by itself proof of an exact rename.

For every step retain the repository, commit and parent, file/line or term
reference, compared contents and checksums. Separate directly observed edits
from the reviewed explanation of their meaning. Use commit messages as context,
not as a substitute for inspecting model/ontology changes. Do not load demo or
production biobank/collection/service records while reconstructing this history.

Match the current API definitions against the fetched upstream definitions.
Do not assume GitHub master is deployed. If several commits contain the same
definitions, report that range of possible revisions rather than inventing one
deployment commit. If no version matches, record the difference and uncertainty.
An upstream commit date is not a Directory deployment date; report separately
when a change was committed and when the live definition was observed.

### Upstream Versus Deployed State

The Directory team's clarification distinguishes release creation from server
installation: development branches merge into master, and each master update
triggers a software release that can be installed on an EMX2 server. Deployed
software therefore comes from master history, but the current master tip is not
necessarily the installed release. Data-model and ontology updates are applied
separately by a data manager, often with data migration; their timing depends on
urgency and migration complexity, not the software release schedule. This is a
team-provided operational explanation, not evidence of any particular deployment
date or migration having completed.

Keep four separately identified observations: the server-reported software build,
the live schema, the live reference vocabularies, and the upstream GitHub revision.
Resolve upstream master to an immutable commit at retrieval time. Read the server
manifest (ImplementationVersion, SpecificationVersion and DatabaseVersion) as
metadata; do not interpret DatabaseVersion as a vocabulary revision. Retain the
target URL, retrieval time and content fingerprints for each observation.

The distinction is demonstrably necessary: on 2026-11-05, the Directory manifest
reported v13.209.1, implementation 573baa460ebed8ac8d3af37b22124ff7f7be96de.
That commit's packaged DataCategories.csv has 15 terms, whereas the observed live
reference table has 24. Software deployment and database vocabulary updates are
therefore not interchangeable version identifiers.

Compare live schema and ontology contents independently with pinned upstream
versions. A content match establishes compatible source versions, not proof of
the exact commit deployed or its deployment date. Where several revisions match,
report the candidates/range. Where none matches, report the actual differences
and leave the source revision unestablished; do not assume master or call an
unexplained difference a deployment failure. Server build metadata is a reported
identity, not independent verification of the running binary.

In the Manual, identify the pinned GitHub revision together with the date/time
when the live production schema and relevant vocabularies were checked, and the
production target/schema. Describe this as an observation, not a deployment date.
Keep detailed fingerprints and software-build metadata in supporting evidence
rather than repeating them throughout the human-facing guidance.

The software commit and model/ontology commits against which the Manual guidance
and QC rules are developed are their authoritative development baselines. Record
those separately from production observations, including in the Manual revision
history. A newer production observation alone must not retarget a rule's baseline.
The software expectation may include an immutable full `revision` alongside its
release; older guidance without that field reports the commit as unrecorded.
Recover historical edition baselines only from supporting evidence. A related
change that postdates an edition is not its development baseline; document the
date conflict rather than inferring a baseline from a release or publication date.

Both QC and the Manual must have one clearly identified version-context summary.
Include the directory-scripts release/commit (and modified state when known),
guidance contract version and content revision/hash, Directory target/schema,
server-reported software release/commit, model reference revision and each
relevant ontology reference revision, production verification date/time, and
current retrieval channel/time. Include the pinned MIABIS revision for conclusions
that rely on it; otherwise mark it not used. The Manual also identifies its own
edition. Distinguish the versions underlying reviewed guidance from the versions
observed in a particular QC run. Do not substitute one software commit for all
these independently maintained components.

Keep the summary readable: short revision IDs linked to immutable full references
and a single supporting evidence record for complete hashes. If a live model or
ontology content match establishes only candidate revisions, say so; if its exact
revision is unknown, report unknown alongside the observed fingerprint and checked
date. Missing server metadata must not prevent otherwise supported offline QC.
Explain master releases, server installation and independently applied model/
ontology migrations next to the Manual summary, and link to this explanation
from QC reference context. Do not imply that normal QC checks MIABIS conformance.

### Non-Blocking QC Compatibility Diagnostics

QC runs with available live/cached inputs; a version mismatch is not by itself
an abort condition. Ship explicit reviewed expectations for the server software
baseline and relevant model/ontology features in the guidance/reference contract.
Distinguish an expected/reference version from a minimum required capability;
do not claim every earlier release is incapable of running the checks.

At the once-per-run reference summary, emit at most one combined version-mismatch
message, listing each differing component's expected and observed versions and
any practical limitation. Its level is WARNING if any demonstrably ordered
component is older than expected; otherwise it is INFO when the known differences
are newer versions only. Thus newer software plus an older model produces one
WARNING, not separate per-component messages. Matching versions require no mismatch
message. Unknown or divergent comparisons must be labelled unverified, not older
or newer; include that uncertainty in the same summary without inventing an
ordering. Missing capabilities can still warrant the separate reduced-coverage
diagnostic described below. The version message is not an entity finding and must
not be repeated per record or in XLSX findings. Ensure the newer-version INFO is
visible in ordinary text output, not hidden unless verbose mode is enabled.
Software comparisons use validated release ordering or evidenced commit ancestry,
not lexical SHA ordering. Model/ontology ordering uses explicit reported revision
information where available, otherwise reviewed historical content matches and
capabilities; never derive it from the software version alone. An unknown,
divergent or mixed model is described as unverified/different, not proven older.

These are local/available-evidence comparisons, not a mandatory live GitHub lookup
at every QC run. Keep offline execution possible. If a field/reference needed for
a particular check is unavailable or incompatible, issue a concise diagnostic and
skip only that unsupported check path; keep supported and unrelated checks active.
Never turn missing capabilities into invented entity errors, silently substitute
current expectations for observed definitions, or promise all checks ran. Summarize
reduced coverage once when relevant. Missing inputs that genuinely prevent any
safe execution still receive the existing clear configuration/input error.

For ordinary QC runs, print reference context once in the text output, outside
individual findings: the pinned GitHub revision and production verification
date, with a clear distinction between that recorded verification and any current
live/cache retrieval. Do not claim a fresh production check when using cached
evidence. Do not repeat version/date metadata in each check message or add it to
the XLSX findings output. Concise per-finding Manual section references remain
appropriate where detailed guidance is needed.

Cache these historical inputs with their exact revisions for offline use.
Missing history, rate limits, unsupported file changes or incomplete downloads
must be visible in the report and prevent a claim that the history is complete.
Produce a readable change history for the Manual: date/source, what changed,
effect on existing records, and the action or extra information needed.

## Directory Metadata API

Extend directory.py with a metadata-only module API, alongside the existing
get_directory_ontology_table. Do not construct Directory for the implementation
audit: its constructor loads entity snapshots and builds data graphs.

The API must provide schema metadata, explicitly selected reference ontologies,
target/schema identity, retrieval channel/time and reference fingerprints.
Reuse the current EMX2 client and shared authentication/configuration patterns.
Authentication precedes private schema selection; public ERIC remains usable
without credentials. Add a public Directory target accessor for data-QC callers
if needed rather than reading its name-mangled target attribute.

Metadata/ontology caches are separate from entity snapshots and keyed by target
URL, schema/table and reference revision as applicable. Preserve normal
cache-first/offline-tolerant behavior with visible cached/fallback status.
An explicit refresh must not purge the user's entity snapshots. Offline mode
must never make a network request and must fail clearly when required inputs
are absent. Never describe cached evidence as a fresh live audit.
Retrieve software manifests independently of schema compatibility. Preserve prior
usable references on partial refresh, with explicit fallback provenance; record
software observations with their own timestamps. Validate local cache identity
and content hashes before use. Unknown optional guidance fingerprints must be
rejected non-fatally rather than reaching replacement selection.

The conformance client is allowlisted to schema metadata, schema discovery and
the required reference tables. Tests must prove it never reads entity records,
creates Directory graphs, fetches contact emails or writes to the server.

## Data QC: Deprecated Values

Introduce a focused VocabularyStatus plugin with the proposed family VOC and a
ERROR-level DeprecatedValue check. Initial fields are Collections.data_categories
and Services.serviceTypes; future vocabularies require explicit scope extensions.
Use current reference definitions plus reviewed guidance, not the display label
alone. For the present source format, only explicit declared deprecation is
recognized; negated, merely historical, or ambiguous mentions are not declarations.
Changes to upstream declaration format must produce a maintenance diagnostic,
not speculative deprecation classifications.

Messages identify the field, deprecated term, reason, replacement options and
what information is needed. Deduplicate repeated values per entity/field.
Keep the immediate action understandable in the QC output; refer to relevant
Manual sections for detailed explanations rather than embedding long guidance.
Guidance entries may carry stable logical section IDs and readable titles.
Validate these against the Manual's LaTeX labels when checking both repositories;
ordinary QC must not require a Manual checkout. Avoid fixed page/chapter numbers.
Use the public Manual entry https://zenodo.org/doi/10.5281/zenodo.2583446 and
verified published PDF anchors where available, not internal Overleaf links or
invented PDF fragments. If a new section is not yet published, say so and keep
enough actionable guidance in QC; never imply it is in the published edition.
For example: "This collection uses the deprecated value IMAGING_DATA. Choose
the image types it actually contains: Body image, Whole slide image or Photo
image. Check the collection's imaging information before changing the value."
Say clearly in the Manual that the API may still accept a legacy value while
current QC requires it to be replaced. Do not call this an upload rejection.
Do not duplicate the existing sample/clinical/image category mismatch conditions.
If guidance is unavailable or invalid, keep checks with sufficient ontology
evidence active, issue a suppressible script diagnostic, and omit unsupported
migration recommendations. Never disable unrelated plugins.

Retired terms that are absent from a new ontology are distinct from deprecated
terms still accepted by it. Old cached values are not automatically current data
errors. Initially report reference/cache compatibility uncertainty as a script
diagnostic with refresh guidance, not fabricated per-entity errors. New assertions
about invalid retired values require coherent source provenance and explicit rules.

No automated Directory updates or qcheck-updater proposals are part of this
initial error-reporting check, including for plausible exact renames.

Support service findings properly throughout shared reporting: add a SERVICE
entity type and its read-only links/filter/export handling rather than disguising
services as collections. Use configured scope and owner context; preserve existing
biobank, collection, contact and network reporting. Do not add service mutation
support to the updater. Existing service-contact/quality API gaps are not silently
included as unrelated fixes.

## Separate MIABIS Conformance Checker

Approved documentation refinement: document this tool and its implementation
comparison findings in `docs/auxiliary-tools.md`, rather than a separate Manual
section. MIABIS bindings have no Manual section links. Manual Section 3.11
explains central update responsibility (BBMRI-ERIC data managers in Common
Service IT), practical migration and version context in nontechnical language;
immutable technical references may sit in a supporting footnote. This refines
the earlier Manual/version-summary presentation requirements without changing
QC or comparison semantics.

Proposed CLI: directory-miabis-conformance.py. Follow common logging, target,
authentication and schema argument conventions. Provide explicit JSON/Markdown
report outputs and an optional LaTeX report fragment, with output overwrite safety.
Do not register it in checks/, emit DataCheckWarning objects, or attach fix plans.

Initial vocabulary scope is DataCategories and ServiceTypes. Schema metadata
establishes how they are referenced and whether relevant structural relationships
exist; this is not a claim to audit the entire MIABIS data model.
The assessment must account for every reference term and every implemented term
in these two vocabularies, including aliases, extensions and unresolved concepts;
it must not stop at a small set of convenient examples or claim a complete audit
from vocabulary counts alone.

Reference baseline proposal for approval: pin official MIABIS commit
272d05e792e312f1fe56e24eac37d43ce9376bf1, all lists.md Dataset Type/Service Type
sections and their linked Core/V3/service-component definitions. Record the
Directory implementation's claimed specification version separately. The CLI
can select another explicit MIABIS revision/profile. Do not invent a published
release designation or automatically follow upstream HEAD.

Resolve linked normative files at the same pinned revision, not embedded mutable
master URLs. Parse only declared table/section formats, validate expected headings
and column meanings, and fail clearly on unsupported source formats. Upstream
source inconsistencies are findings about the reference, not Directory defects.
Assess the selected component attribute tables and their inline allowed values
against the consolidated lists; downloading these files is not sufficient.
Retain their cardinalities and development-status context. Differences requiring
interpretation, such as the Collection component's cardinality 1 versus a
multi-value Directory dataset field, belong in the implementation report and
Manual, not entity-level QC errors.

Match observed ontologies and model structure to historical source intervals,
including unchanged endpoints and rename histories. Multiple matching intervals
remain candidates, never a unique deployment claim. Model matching covers the
business type/required/key/reference projection; descriptions, defaults, validation
and unexposed read-only properties are not thereby certified. Explain unmatched
terms/properties and retain expected/observed definitions and source locators.

Comparison separates:
- exact representations and reviewed name/label aliases;
- missing standard concepts and unsupported claimed equivalences;
- semantic broadening/narrowing or ambiguous interpretation requiring review;
- documented Directory extensions versus unexplained additions;
- differences in definitions, identifiers or relationships actually specified
  by MIABIS, not properties invented by the implementation audit;
- source-version/publication uncertainty and reference-source inconsistencies.

Whitespace/case/punctuation normalization alone must not establish conceptual
equivalence. Use explicit source identifiers where present; otherwise reviewed
bindings/interpretations in the guidance JSON. Do not claim that a text-difference
algorithm establishes semantic compliance. Candidate semantic differences remain
review-required unless supported by explicit evidence or reviewed guidance.
An extra Directory term is not automatically an error. Directory service-category
assignments cannot violate MIABIS requirements that MIABIS does not specify.

Reports carry target/schema, source revisions/URLs/checksums, data freshness,
stable finding identities, expected/observed evidence, classification, consequence
and limitations. No entity IDs or individual source responses are needed.
The human-readable report must explain differences in ordinary language, for
example "Directory has an additional term" or "This Directory term has a more
specific meaning than the MIABIS term". Internal JSON keys may use technical
names, but must not become unexplained report headings. Include the relevant
change history, not just a comparison of the current lists.
Exit status: 0 for a complete audit without unreviewed discrepancies; 1 for a
complete comparison requiring review; 2 for incomplete/unsupported/unavailable
inputs. Partial reports must say no complete conformance conclusion is available.
Reviewed extensions must remain visible even when they do not make the run fail.

The checker writes explicit local reports only. A maintainer reviews its findings
before incorporating the relevant LaTeX material in the Manual; it does not
overwrite reviewed manual guidance or publish a PDF automatically.

## Additional Consistency-Check Assessment

Deliver a documented evidence-backed assessment, not an unapproved new rule set.
For each candidate, identify fields, logical implication, existing overlapping
checks, counterexamples, certainty and suggested severity or review-only status.

Candidates include specific imaging dataset classes versus declared data
categories, metadata conflicts that remain undetected after the category renames,
and service vocabulary/reference requirements. Preserve mixed-content collections.
Explicit negative examples: genomic datasets do not require locally held DNA;
DNA samples do not imply genomic datasets; a sequencing service does not imply
that genomic datasets are held; a research specialization is not automatically
an operational service. Unknown/partial descriptions are not proven contradictions.

Assess gaps using schema/reference definitions first. Any later entity-data
analysis belongs to a separately identified data-QC activity, never to the
schema-only conformance checker. New warning conditions beyond deprecated-value
checks need their own explicit reviewed rule approval before implementation.

## Manual And Documentation

Add a Recent changes and migration guidance section within the Manual's Data
model chapter, with dataset, service and network subsections. Separate routine
curator actions from implementation discrepancies. Cite specification versions,
immutable upstream evidence and review dates, not guessed deployment dates.

Expanded LaTeX prose/examples are maintained in the Manual repository. Stable
source-comment references identify the relevant guidance IDs and reviewed content
fingerprints from directory-scripts JSON. The documentation maintenance validator
flags missing IDs and changes requiring prose review; it must not automatically
declare that unchanged prose still agrees with changed guidance. Any generated
LaTeX tables are derived from JSON, never a second manually maintained database.

Write guidance for data managers, not for parser implementers. Avoid unexplained
terms such as "semantic alignment", "source coherence" or "provenance matrix".
Use concrete examples and state exactly what a curator should inspect or ask.
Keep technical identifiers/evidence available through labelled references or
notes without making long hashes and implementation details the main text.

Network guidance must explicitly document:
- no automatic membership inheritance from biobank to collection, between parent
  and child collections, or through former parent networks;
- removal of combined_network and parent_network fields;
- recording confirmed membership on each relevant entity's network field;
- reviewing historical inherited membership before explicitly materializing it,
  not copying all parent memberships blindly;
- inverse network membership links are not a second independent membership source.
Review domain-specific cohort/network checks for hidden inheritance assumptions
without deleting valid, separately justified membership-policy rules.
This review delivers findings and proposed corrections only. It does not authorize
changing existing cohort/network warning predicates in this project. Confirmed
problems must be described in the assessment; behavioral fixes require a separately
approved rule change with its regression contract. Do not silently call an issue
fixed merely because its behavior was documented.

Put normal QC operation in docs/data-quality.md and the standalone checker in
docs/auxiliary-tools.md. Add architectural/data contracts to DEVELOPMENT.md and
only genuinely new repository-wide guardrails to AGENTS.md. Keep README concise.
Update manual-generation instructions and test generated CHECK_DOCS references.

## Acceptance And Verification

- JSON validation, stable IDs, evidence locators, version applicability, exact
  versus ambiguous mappings and no fabricated replacement assertions.
- Reference fetching/caching, immutable revisions, offline mode, target isolation,
  authentication order and explicit incomplete-source diagnostics.
- Complete relevant GitHub history, pagination, file renames, restored terms,
  upstream-versus-deployed version differences and no invented deployment dates.
- Metadata-only network-call spies proving entity tables and mutations are unused.
- Exact/alias/missing/extra/deprecated/reference-conflict conformance fixtures;
  source parsing fails rather than silently inventing or dropping table entries.
- ERROR severity for deprecated collection/service values, no duplicate category checks, no updater
  proposals, withdrawn scope, invalid guidance fallback and stale-snapshot safety.
- Service entity reporting preserves existing entity types and output isolation.
- Manual guidance-reference synchronization, readable migration tables, explicit
  network examples, and separate implementation-discrepancy reporting.
- Review representative Manual, QC and audit text for understandable wording and
  concrete next steps; test approved message examples instead of a jargon blacklist.
- Regression gate includes CollectionContent, directory metadata/offline tests,
  reporting/suppressions, manual generator, docstring/Markdown contracts, and the
  full suite in an isolated temporary checkout. Record baseline failures separately.
- Rebuild the Manual with glossary/references settled and inspect representative
  migration, conformance and check pages. Preserve existing local PDFs/inputs.
- Review complete deltas in both repositories; commit separately only when
  requested and do not push without authorization. No permanent feature worktree
  or additional environment installation is required by this design.

## Builder Discretion And Approval Calls

The builder may settle internal helper names, parser implementation, precise
JSON schema field spelling and test organization, provided these contracts hold.
No user approval is implied for automatic data updates, arbitrary semantic checks,
global ontology coverage, unrelated service API fixes, publication or installation.

Calls proposed here: initial two-vocabulary scope; report-only ERROR findings for deprecated-value
QC; no retired-value accusations from version-uncertain caches; explicit pinned
MIABIS reference rather than an assumed v4 release; no implementation of additional
consistency-check candidates until the specific rules are separately approved.

Builder check: an independent Sol medium review raised initial guidance coverage
and the boundary of network-QC corrections. The explicit full-coverage and
analysis-only network-review decisions above resolve those planning ambiguities;
they remain visible calls for the user's approval of this design.
